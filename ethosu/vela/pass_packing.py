# Copyright (C) 2020 Arm Limited or its affiliates. All rights reserved.
#
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the License); you may
# not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an AS IS BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


# Description:
# Packs a subgraph with Neural Network Operations into Passes. Each Pass has one or more Operations.

from .nn_graph import Operation, Pass, PassPlacement, TensorPurpose, NpuBlockType, Tensor
import collections
import enum
from .data_type import BaseType, DataType


class PassFlags(enum.Flag):
    Empty = 0
    Pre = 1
    Main = 2
    Post = 4
    Mac = 8
    Dma = 32
    ElementWise = 256
    Npu = 512
    Cpu = 1024
    StartupInit = 2048
    MemoryOnly = 4096
    PostFusingLimited = 8192


npu_pre_ops = set(("QuantizedResizeBilinear", "SplitSliceRead",))

mac_main_ops = set(
    (
        # convolutions
        "Conv2DBiasAct",
        "Conv2D",
        "QuantizedConv2D",
        "Conv2DBackpropInputSwitched",
        # depth-wise convolutions
        "DepthwiseConv2dBiasAct",
        "DepthwiseConv2dNative",
        "QuantizedDepthwiseConv2D",
        # FC layers
        "QuantizedMatMul",
        "MatMul",
        "FullyConnectedAct",
        # RNN/LSTM/GRU
        "BlockLSTM",
        # pooling
        "QuantizedMaxPool",
        "QuantizedAvgPool",
        "AvgPool",
        "MaxPool",
        "AvgPoolAct",
        "MaxPoolAct",
    )
)

binary_elem_wise_main_ops = set(
    (
        # binary element-wise
        "AddAct",
        "MulAct",
        "SubAct",
        "QuantizedAdd",
        "QuantizedSub",
        "QuantizedMul",
        "Mul",
        "Add",
        "Sub",
        "Minimum",
        "Maximum",
    )
)

unary_elem_wise_main_ops = set(("LeakyRelu", "Abs"))  # Unary element-wise operations

elem_wise_main_ops = binary_elem_wise_main_ops | unary_elem_wise_main_ops

activation_ops = set(("QuantizedRelu", "QuantizedRelu1", "QuantizedRelu6", "Relu", "Relu6", "ReluN1To1"))
npu_post_ops = activation_ops | set(
    # Bias-add operations: Get rid of these once we have rewrites from Conv2D + BiasAdd + Activation to Conv2DBiasAct.
    ("Mul", "Add", "QuantizedBiasAdd", "Requantize", "QuantizedBatchNorm", "BiasAdd", "FusedBatchNorm")
)

npu_post_fuse_limited_ops = set(
    # Set of post operators that should not be fused with main/elementwise ops
    ("ConcatSliceWrite", "Sigmoid", "Tanh")
)

elem_wise_ops = elem_wise_main_ops | activation_ops | set(("Sigmoid", "Tanh"))


quantization_ops = set(("Dequantize", "QuantizeV2", "Max", "Min"))
cpu_ops = (
    set(("Softmax", "QuantizedSoftmax", "LRN", "Shape", "QuantizedPad", "Pad", "AddN"))
    | quantization_ops
)

npu_dma_ops = set(("DMA",))
startup_init_ops = set(("Const", "VariableV2", "Placeholder", "SubgraphInput"))
memory_only_ops = set(("Squeeze", "Reshape", "QuantizedReshape", "ExpandDims",))


test_sequence = [
    (
        # ops_set
        npu_post_ops,
        # incompatible_pack_flags
        PassFlags.Cpu | PassFlags.MemoryOnly | PassFlags.Pre | PassFlags.Main,
        # flags_to_set
        PassFlags.Npu | PassFlags.Post,
        # flags_to_clear
        PassFlags.Empty,
    ),
    (
        # ops_set
        npu_post_fuse_limited_ops,
        # incompatible_pack_flags
        PassFlags.Cpu | PassFlags.MemoryOnly | PassFlags.Pre | PassFlags.Main,
        # flags_to_set
        PassFlags.Npu | PassFlags.PostFusingLimited,
        # flags_to_clear
        PassFlags.Empty,
    ),
    (
        # ops_set
        mac_main_ops,
        # incompatible_pack_flags
        PassFlags.Cpu
        | PassFlags.MemoryOnly
        | PassFlags.ElementWise
        | PassFlags.Pre
        | PassFlags.Main
        | PassFlags.PostFusingLimited,
        # flags_to_set
        PassFlags.Npu | PassFlags.Mac | PassFlags.Main,
        # flags_to_clear
        PassFlags.Empty,
    ),
    (
        # ops_set
        elem_wise_main_ops,
        # incompatible_pack_flags
        PassFlags.Cpu
        | PassFlags.MemoryOnly
        | PassFlags.Mac
        | PassFlags.Pre
        | PassFlags.Main
        | PassFlags.PostFusingLimited,
        # flags_to_set
        PassFlags.Npu | PassFlags.ElementWise | PassFlags.Main,
        # flags_to_clear
        PassFlags.Empty,
    ),
    (
        # ops_set
        npu_pre_ops,
        # incompatible_pack_flags
        PassFlags.Cpu | PassFlags.MemoryOnly,
        # flags_to_set
        PassFlags.Npu | PassFlags.Mac | PassFlags.Pre | PassFlags.ElementWise,
        # flags_to_clear
        PassFlags.Empty,
    ),
    (
        # ops_set
        npu_dma_ops,
        # incompatible_pack_flags
        PassFlags.Cpu | PassFlags.MemoryOnly,
        # flags_to_set
        PassFlags.Npu | PassFlags.Dma,
        # flags_to_clear
        PassFlags.Empty
    ),
    (
        # ops_set
        startup_init_ops,
        # incompatible_pack_flags
        PassFlags.Npu | PassFlags.Cpu | PassFlags.MemoryOnly,
        # flags_to_set
        PassFlags.StartupInit | PassFlags.Main,
        # flags_to_clear
        PassFlags.Empty,
    ),
    (
        # ops_set
        memory_only_ops,
        # incompatible_pack_flags
        PassFlags.Npu | PassFlags.Cpu,
        # flags_to_set
        PassFlags.MemoryOnly | PassFlags.Main,
        # flags_to_clear
        PassFlags.Empty
    ),
    (
        # ops_set
        cpu_ops,
        # incompatible_pack_flags
        PassFlags.Npu | PassFlags.MemoryOnly | PassFlags.Main,
        # flags_to_set
        PassFlags.Cpu | PassFlags.Main,
        # flags_to_clear
        PassFlags.Empty
    ),
    (   # This last one is a fallback for unrecognised operations
        # ops_set
        None,
        # incompatible_pack_flags
        PassFlags.Npu | PassFlags.MemoryOnly | PassFlags.Main,
        # flags_to_set
        PassFlags.Cpu | PassFlags.Main,
        # flags_to_clear
        PassFlags.Empty
    ),
]

# Some sanity checking
for (operation_set, incompatible_pack_flags, flags_to_set, flags_to_clear) in test_sequence:
    assert not flags_to_clear & flags_to_set

    if operation_set is not None:
        for op in operation_set:
            assert len(op) > 1  # This is to avoid string literals being decomposed


def pack_into_passes(nng, arch, verbose_packing=False):
    def visit_op(op, ignored):
        visit_op_refcount[op] += 1

        if visit_op_refcount[op] == 1:  # First-time visit, go and fix up unused output tensors
            for tens in op.outputs:
                if len(tens.consumers()) == 0:
                    visit_op_refcount[op] += 1

        assert visit_op_refcount[op] <= len(op.outputs)
        if visit_op_refcount[op] == len(op.outputs):

            if op.type in startup_init_ops:
                startup_list.append(op)
            else:
                _, _, _, ofm_tensor = op.get_ifm_ifm2_weights_ofm()
                if ofm_tensor is None:
                    ofm_tensor = op.outputs[0]
                build_pass((op,), ofm_tensor)

    def build_pass(start_ops_to_process, ofm_tensor=None):
        reverse_ops_list = []
        curr_flags = PassFlags.Empty
        npu_block_type = NpuBlockType.Default

        reverse_intermediates = []
        input_set = set()
        ifm_tensor = None
        primary_op = None

        to_process = collections.deque()
        for start_op in start_ops_to_process:
            to_process.append((start_op, None))

        while to_process:
            curr_op, tens = to_process.popleft()

            if curr_op in reverse_ops_list:
                continue

            for operation_set, incompatible_pack_flags, flags_to_set, flags_to_clear in test_sequence:
                if operation_set is None or curr_op.type in operation_set:
                    if not (curr_flags & incompatible_pack_flags):
                        if flags_to_set & PassFlags.Npu:
                            if not curr_op.run_on_npu:
                                continue

                        reverse_ops_list.append(curr_op)
                        new_block_type = curr_op.attrs.get("npu_block_type", NpuBlockType.Default)
                        if new_block_type != NpuBlockType.Default:
                            assert npu_block_type == NpuBlockType.Default
                            npu_block_type = new_block_type  # Only one major block type per pass
                            assert primary_op is None
                            primary_op = curr_op

                        curr_flags &= ~flags_to_clear
                        curr_flags |= flags_to_set

                        if flags_to_set & PassFlags.Npu:
                            if flags_to_set & (
                                PassFlags.Mac | PassFlags.ElementWise | PassFlags.Post | PassFlags.PostFusingLimited
                            ):
                                assert len(curr_op.inputs) >= 1
                                if curr_op.type == "BlockLSTM":
                                    ifm_tensor = curr_op.inputs[3]
                                else:
                                    ifm_tensor = curr_op.inputs[0]
                                assert ifm_tensor.purpose == TensorPurpose.FeatureMap

                        if flags_to_set & PassFlags.Dma:
                            # DMAs are special - Output buffers need to be preserved as intermediates,
                            # if the pass consumes the results
                            if tens is not None:
                                reverse_intermediates.append(tens)

                        if operation_set is None:
                            print("Warning:", curr_op.type, "operation is unknown or unsupported, placing on CPU")

                        for inp in curr_op.inputs:
                            can_pack = True
                            if len(inp.ops) == 1:
                                next_op = inp.ops[0]
                                for outp in next_op.outputs:
                                    consumers = outp.consumers()
                                    if len(consumers) > 1 or (len(consumers) == 1 and consumers[0] != curr_op):
                                        can_pack = False
                                        break
                            else:
                                can_pack = False

                            if can_pack:
                                to_process.append((next_op, inp))
                            else:
                                assert inp is not None
                                input_set.add(inp)

                        break

            else:
                # This operation is not compatible with already packed operations, just register the tensor as an input
                assert tens is not None
                input_set.add(tens)

        if curr_flags & PassFlags.Npu and not curr_flags & (PassFlags.ElementWise | PassFlags.Mac):
            # Make the choice that if we don't have a mac operation, the ambidextrous operations go on the
            # element wise unit
            curr_flags |= PassFlags.ElementWise

        is_element_wise = True
        for op in reverse_ops_list:
            if not op.type in elem_wise_ops and not op.type in npu_dma_ops:
                is_element_wise = False
                break

        placement = PassPlacement.Unknown
        if curr_flags & PassFlags.Npu:
            assert placement == PassPlacement.Unknown
            placement = PassPlacement.Npu
        if curr_flags & PassFlags.Cpu:
            assert placement == PassPlacement.Unknown
            placement = PassPlacement.Cpu
        if curr_flags & PassFlags.MemoryOnly:
            assert placement == PassPlacement.Unknown
            placement = PassPlacement.MemoryOnly
        if curr_flags & PassFlags.StartupInit:
            assert placement == PassPlacement.Unknown
            placement = PassPlacement.StartupInit
        assert placement != PassPlacement.Unknown

        ops_list = list(reversed(reverse_ops_list))
        intermediates = list(reversed(reverse_intermediates))

        if primary_op == None:
            primary_op = create_primary_op(ops_list)
            if primary_op != None:
                visit_tensor_refcount[primary_op.inputs[0]] += 1
                npu_block_type = primary_op.attrs["npu_block_type"]
                for input_tens in primary_op.inputs:
                    if input_tens not in input_set:
                        input_set.add(input_tens)

        ordered_input_list = []
        input_refcounts = collections.defaultdict(int)
        for op in ops_list:
            for inp in op.inputs:
                if inp in input_set:
                    if input_refcounts[inp] == 0:
                        ordered_input_list.append(inp)
                    input_refcounts[inp] += 1

        name = ops_list[0].name
        non_dma_ops = [op for op in ops_list if op.type != "DMA"]
        if non_dma_ops:
            name = non_dma_ops[0].name
        ps = Pass(name, placement, is_element_wise, npu_block_type)
        ps.ops = ops_list
        ps.primary_op = primary_op
        ps.inputs = ordered_input_list
        ps.intermediates = intermediates
        ps.outputs = list(ops_list[-1].outputs)
        ps.ifm_tensor = ifm_tensor

        # ElementWise operation, 2 IFMs
        if ps.primary_op and ps.primary_op.type in binary_elem_wise_main_ops:
            ps.ifm_tensor = ps.inputs[0]

            if len(ps.inputs) == 1:
                # Only 1 input, IFM and IFM2 are the same tensor
                ps.ifm2_tensor = ps.inputs[0]
            else:
                ps.ifm2_tensor = ps.inputs[1]
        else:
            ps.ifm_tensor = ifm_tensor
            ps.ifm2_tensor = None

        ps.ofm_tensor = ofm_tensor
        assert ps.placement != PassPlacement.Npu or ps.ofm_tensor is not None
        ps.weight_tensor = ps.get_primary_op_ifm_weights()[1]
        ps.scale_tensor = ps.get_primary_op_ifm_weights_biases_ofm()[2]

        for op in ps.ops:
            op.scheduled_pass = ps

        reverse_pass_list.append(ps)

        for inp, refcount in input_refcounts.items():
            for _ in range(refcount):
                visit_tensor(inp)

        return ps

    def visit_tensor(tens):
        visit_tensor_refcount[tens] += 1
        assert visit_tensor_refcount[tens] <= len(tens.consumers())
        if visit_tensor_refcount[tens] == len(tens.consumers()):
            for op in reversed(tens.ops):
                visit_op(op, tens)

    def create_primary_op(ops_list):
        if any(op.type in (npu_pre_ops | npu_post_ops | npu_post_fuse_limited_ops) for op in ops_list):
            # Configure a 1x1 AvgPool and attach the op onto it
            op = ops_list[0]
            inp = op.inputs[0]
            avgpool_name = op.name + "_avgpool"
            avgpool_op = Operation("AvgPool", avgpool_name)
            avgpool_op.inputs = [inp]
            avgpool_op.inputs[0].consumer_list.append(avgpool_op)
            avgpool_op.attrs["padding"] = b"VALID"
            avgpool_op.attrs["npu_block_type"] = NpuBlockType.Pooling
            avgpool_op.attrs["stride_w"] = 1
            avgpool_op.attrs["stride_h"] = 1
            avgpool_op.attrs["filter_width"] = 1
            avgpool_op.attrs["filter_height"] = 1
            avgpool_op.attrs["strides"] = [1, 1, 1, 1]
            avgpool_op.attrs["ksize"] = [1, 1, 1, 1]
            avgpool_op.attrs["skirt"] = [0, 0, 0, 0]
            avgpool_op.attrs["explicit_padding"] = [0, 0, 0, 0]
            avgpool_out = inp.clone("_avgpooled")
            avgpool_out.consumer_list.append(op)
            avgpool_out.ops = [avgpool_op]
            avgpool_op.outputs = [avgpool_out]

            op.inputs[0] = avgpool_out
            ops_list.insert(0, avgpool_op)

            return avgpool_op

        return None

    for sg in nng.subgraphs:
        reverse_pass_list = []
        visit_op_refcount = collections.defaultdict(int)
        visit_tensor_refcount = collections.defaultdict(int)

        startup_list = []

        for tens in sg.output_tensors:
            visit_tensor(tens)

        if startup_list:
            startup_ps = build_pass(startup_list)
            startup_ps.outputs = [op.outputs[0] for op in startup_list]  # Need to fixup the outputs
            startup_ps.name = "startup_weight_initialisation"

        sg.passes = list(reversed(reverse_pass_list))
        sg.build_pass_links()

    if verbose_packing:
        nng.print_passes()

    return nng