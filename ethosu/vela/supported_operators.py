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
# The SupportedOperators class which is a collection of all supported operators and parameter checks.
from collections import defaultdict

import numpy as np

from .data_type import BaseType
from .data_type import DataType
from .numeric_util import is_integer
from .operation import get_slice_offsets
from .operation import Op
from .tensor import check_quantized_tens_scaling_equal
from .tflite_mapping import BUILTIN_OPERATOR_UNKNOWN
from .tflite_mapping import optype_to_builtintype


# Custom decorator function to allow formatting docstrings containing "{}"
def docstring_format_args(args):
    def docstring(func):
        func.__doc__ = func.__doc__.format(*args)
        return func

    return docstring


def _optype_formatter(op_list):
    # Convert internal op types to external names
    output = map(optype_to_builtintype, op_list)
    # Remove UNKNOWNs
    output = (x for x in output if x is not BUILTIN_OPERATOR_UNKNOWN)
    # Order alphabetically and join into a string representation
    return ", ".join(str(op) for op in sorted(output))


class SupportedOperators:
    # Categorised lists of supported operators
    npu_pre_ops = set((Op.SplitSliceRead,))
    convolution_ops = set((Op.Conv2DBias, Op.Conv2D, Op.QuantizedConv2D,))
    depthwise_convolution_ops = set((Op.DepthwiseConv2DBias,))
    transpose_convolution_ops = set((Op.Conv2DBackpropInput,))
    convolution_like_ops = convolution_ops | depthwise_convolution_ops | transpose_convolution_ops
    max_pooling_ops = Op.op_set(Op.is_maxpool_op)
    avg_pooling_ops = Op.op_set(Op.is_avgpool_op)
    pooling_ops = set((Op.ReduceSum,)) | max_pooling_ops | avg_pooling_ops
    resizing_ops = set((Op.ResizeBilinear,))
    fc_vector_products = set((Op.QuantizedMatMul, Op.MatMul, Op.FullyConnected,))
    mac_main_ops = (
        # RNN/LSTM/GRU
        set((Op.BlockLSTM,))
        # conv/depthwiseconv/transposeconv
        | convolution_like_ops
        # pooling
        | pooling_ops
        # resizing/upscaling
        | resizing_ops
        # FC layers
        | fc_vector_products
    )
    unary_elem_wise_main_ops = Op.op_set(Op.is_unary_elementwise_op)
    binary_elem_wise_min_max_ops = set((Op.Minimum, Op.Maximum,))
    binary_elem_wise_shift_ops = set((Op.SHL, Op.SHR,))
    binary_elem_wise_add_mul_sub = set((Op.Add, Op.Mul, Op.Sub,))
    binary_elem_wise_main_ops = binary_elem_wise_min_max_ops | binary_elem_wise_add_mul_sub | binary_elem_wise_shift_ops
    elem_wise_main_ops = binary_elem_wise_main_ops | unary_elem_wise_main_ops
    supported_int32_tensor_ops = (
        set((Op.ReduceSum, Op.CLZ,)) | binary_elem_wise_add_mul_sub | binary_elem_wise_shift_ops
    )
    relu_ops = Op.op_set(Op.is_relu_op)
    activation_ops = relu_ops | set((Op.Tanh, Op.Sigmoid, Op.Softmax,))
    npu_post_ops = (
        # activation functions
        activation_ops
        # concatenation write direction
        | set((Op.ConcatSliceWrite,))
        # Quantization
        | set((Op.Quantize,))
    )
    split_ops = set((Op.Split, Op.SplitV, Op.StridedSlice, Op.Slice, Op.UnpackReshaped, Op.Unpack,))
    concat_ops = set((Op.Concat, Op.ConcatTFLite, Op.PackReshaped, Op.Pack,))
    memory_only_ops = set((Op.Squeeze, Op.Reshape, Op.QuantizedReshape,)) | concat_ops | split_ops
    shapeless_input_ops = binary_elem_wise_main_ops | set((Op.Split, Op.SplitV,))
    per_axis_quant_ops = convolution_like_ops  # per-axis/channel quantization only currently supported for conv ops
    supported_fused_activations = relu_ops | set((Op.Tanh, Op.Sigmoid, Op.LUT,))
    supported_operators = npu_pre_ops | mac_main_ops | elem_wise_main_ops | npu_post_ops | memory_only_ops
    # Supported data types
    supported_op_dtypes = set((DataType.uint8, DataType.int8, DataType.int16, DataType.int32))
    supported_bias_dtypes = set((DataType.int32, DataType.int64))
    # Defined ranges for allowed values:
    tens_dim_range = (1, 65535)
    stride_range = (1, 3)
    dilation_range = (1, 2)
    dilated_height_range = (1, 64)
    dilated_product_range = (1, 64 * 64)
    weights_limit = 127 * 65536
    filter_range = (1, 8)
    filter_height_range = (1, 256)
    filter_product_range = (1, 256 * 256)
    # Ordered, external names of op types for the constraint reasons
    docstring_shapeless_input_ops = _optype_formatter(shapeless_input_ops)
    docstring_supported_int32_tensor_ops = _optype_formatter(supported_int32_tensor_ops)
    docstring_supported_fused_activations = _optype_formatter(supported_fused_activations)
    docstring_per_axis_quant_ops = _optype_formatter(per_axis_quant_ops)

    def __init__(self):
        # Setup the generic constraints. Note: the order matters
        self.generic_constraints = []
        self.generic_constraints.append(SupportedOperators.constraint_tens_no_dynamic)
        self.generic_constraints.append(SupportedOperators.constraint_tens_defined_shape)
        self.generic_constraints.append(SupportedOperators.constraint_tens_output_scalar)
        self.generic_constraints.append(SupportedOperators.constraint_tens_input_scalar)
        self.generic_constraints.append(SupportedOperators.constraint_tens_shape_size)
        self.generic_constraints.append(SupportedOperators.constraint_tens_dtype)
        self.generic_constraints.append(SupportedOperators.constraint_tens_int32_ops)
        self.generic_constraints.append(SupportedOperators.constraint_tens_dimension)
        self.generic_constraints.append(SupportedOperators.constraint_tens_quant_none_check)
        self.generic_constraints.append(SupportedOperators.constraint_tens_quant_scale)
        self.generic_constraints.append(SupportedOperators.constraint_tens_quant_per_axis)
        self.generic_constraints.append(SupportedOperators.constraint_faf)

        # Setup specific constraints. Note: the order matters
        self.specific_constraints = defaultdict(list)

        # Conv-like checks:
        for op_type in SupportedOperators.convolution_like_ops:
            self.specific_constraints[op_type].append(SupportedOperators.constraint_stride_type)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_stride_range)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_dilation_type)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_dilation_range)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_dilated_height_range)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_dilated_product_range)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_weights_type)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_weights_const)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_weights_limit)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_bias_type)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_bias_40bit)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_batch_size)
        # Depthwise Conv specific checks:
        for op_type in SupportedOperators.depthwise_convolution_ops:
            self.specific_constraints[op_type].append(SupportedOperators.constraint_depth_multiplier)
        # Transpose Conv specific checks:
        for op_type in SupportedOperators.transpose_convolution_ops:
            self.specific_constraints[op_type].append(SupportedOperators.constraint_tconv_stride)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_tconv_same)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_tconv_valid)

        # Pooling checks:
        for op_type in SupportedOperators.pooling_ops:
            self.specific_constraints[op_type].append(SupportedOperators.constraint_batch_size)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_stride_type)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_stride_range)
        # AVG pooling specific checks:
        for op_type in SupportedOperators.avg_pooling_ops:
            self.specific_constraints[op_type].append(SupportedOperators.constraint_matching_in_out_types)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_filter_type)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_filter_range)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_filter_height_range_valid_pad)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_filter_product_range_valid_pad)
        # MAX pooling specific checks:
        for op_type in SupportedOperators.max_pooling_ops:
            self.specific_constraints[op_type].append(SupportedOperators.constraint_matching_in_out_types)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_filter_type)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_filter_height_range)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_filter_product_range)
        # TODO: Check ReduceSum restrictions

        # Relu specific checks:
        for op_type in SupportedOperators.relu_ops:
            self.specific_constraints[op_type].append(SupportedOperators.constraint_quant_scale_inf)

        # Resizing specific checks:
        for op_type in SupportedOperators.resizing_ops:
            self.specific_constraints[op_type].append(SupportedOperators.constraint_resize)

        # Vector Product specific checks:
        for op_type in SupportedOperators.fc_vector_products:
            self.specific_constraints[op_type].append(SupportedOperators.constraint_weights_type)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_weights_const)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_bias_type)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_bias_40bit)

        # Concat specific checks:
        for op_type in (Op.Concat, Op.ConcatTFLite):
            self.specific_constraints[op_type].append(SupportedOperators.constraint_axis_exists)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_axis_valid)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_matching_dimensionality)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_valid_dimensions)

        # Element-wise checks:
        for op_type in SupportedOperators.elem_wise_main_ops:
            self.specific_constraints[op_type].append(SupportedOperators.constraint_elemwise_batch_size)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_matching_either_shapes)
        # Unary specific checks:
        for op_type in SupportedOperators.unary_elem_wise_main_ops:
            self.specific_constraints[op_type].append(SupportedOperators.constraint_matching_in_out_types)
        # Binary Min/Max specific checks:
        for op_type in SupportedOperators.binary_elem_wise_min_max_ops:
            self.specific_constraints[op_type].append(SupportedOperators.constraint_matching_in_out_types)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_matching_quantization_parameters)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_broadcast_shapes)
        # Binary Add/Mul/Sub specific checks:
        for op_type in SupportedOperators.binary_elem_wise_add_mul_sub:
            self.specific_constraints[op_type].append(SupportedOperators.constraint_matching_inputs_types)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_matching_signed)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_unsigned_valid)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_broadcast_shapes)
        # Binary Shift specific checks:
        for op_type in SupportedOperators.binary_elem_wise_shift_ops:
            self.specific_constraints[op_type].append(SupportedOperators.constraint_inputs_int32)
            self.specific_constraints[op_type].append(SupportedOperators.constraint_broadcast_shapes)

        # SHL specific checks:
        self.specific_constraints[Op.SHL].append(SupportedOperators.constraint_output_int32)

        # CLZ specific checks:
        self.specific_constraints[Op.CLZ].append(SupportedOperators.constraint_output_int32)

        # Softmax specific checks:
        self.specific_constraints[Op.Softmax].append(SupportedOperators.constraint_matching_shapes)
        self.specific_constraints[Op.Softmax].append(SupportedOperators.constraint_matching_in_out_types)
        self.specific_constraints[Op.Softmax].append(SupportedOperators.constraint_beta_value_range)

        # SplitV specific checks:
        self.specific_constraints[Op.SplitV].append(SupportedOperators.constraint_splitv_inferred)

        # StridedSlice specific checks:
        self.specific_constraints[Op.StridedSlice].append(SupportedOperators.constraint_stridedslice_input_count)
        self.specific_constraints[Op.StridedSlice].append(SupportedOperators.constraint_stridedslice_inputs_const)
        self.specific_constraints[Op.StridedSlice].append(SupportedOperators.constraint_stridedslice_stride_values)
        self.specific_constraints[Op.StridedSlice].append(SupportedOperators.constraint_ellipsis_mask)
        self.specific_constraints[Op.StridedSlice].append(SupportedOperators.constraint_axis_masks)
        self.specific_constraints[Op.StridedSlice].append(SupportedOperators.constraint_slice_ranges)

        # LeakyRelu specific checks:
        self.specific_constraints[Op.LeakyRelu].append(SupportedOperators.constraint_alpha_valid)

    def is_operator_supported(self, op):
        ext_type = optype_to_builtintype(op.type)
        if op.type not in SupportedOperators.supported_operators:
            if op.type not in (Op.Placeholder, Op.SubgraphInput, Op.Const):
                print(f"Info: {ext_type} '{op.name}' is a CPU only op")
            return False

        for constraint in self.generic_constraints + self.specific_constraints[op.type]:
            valid, extra = constraint(op)
            if not valid:
                print(f"Warning: {ext_type} '{op.name}' is not supported on the NPU. Placing on CPU instead")
                print(f" - {constraint.__doc__}")
                if extra:
                    print(f"   {extra}")
                return False

        return True

    @staticmethod
    def constraint_tens_no_dynamic(op):
        "Input(s) and Output tensors must not be dynamic"
        valid = True
        extra = []
        tensors = [tens for tens in op.inputs + op.outputs if tens]
        for tens in tensors:
            if (tens.shape == []) and (tens.values is None):
                valid = False
                extra.append(tens.name)
        extra = ", ".join(extra)
        return valid, f"Op has dynamic tensor(s): {extra}"

    @staticmethod
    def constraint_tens_defined_shape(op):
        "Input(s) and Output tensors must have a defined shape"
        valid = True
        extra = []
        tensors = [tens for tens in op.inputs + op.outputs if tens]
        for tens in tensors:
            if not tens.has_fully_defined_shape():
                valid = False
                extra.append(f"Tensor '{tens.name}' has shape: {tens.shape}")
        return valid, ", ".join(extra)

    @staticmethod
    def constraint_tens_output_scalar(op):
        "Output tensors cannot be scalar"
        ofm = op.ofm
        valid = ofm.shape != []
        return valid, f"Output Tensor '{ofm.name}' is scalar"

    @classmethod
    @docstring_format_args([docstring_shapeless_input_ops])
    def constraint_tens_input_scalar(cls, op):
        "Scalar Input tensors are only valid for op type: {}"
        valid = True
        extra = []
        tensors = [tens for tens in op.inputs if tens]
        for tens in tensors:
            if (tens.shape == []) and (op.type not in cls.shapeless_input_ops):
                valid = False
                extra.append(tens.name)
        extra = ", ".join(extra)
        return valid, f"Op has scalar input tensor(s): {extra}"

    @staticmethod
    def constraint_tens_shape_size(op):
        "Input(s) and Output tensors must not be greater than 4D"
        valid = True
        extra = []
        tensors = [tens for tens in op.inputs + op.outputs if tens]
        for tens in tensors:
            if len(tens.shape) > 4:
                valid = False
                extra.append(f"Tensor '{tens.name}' has shape: {tens.shape}")
        return valid, ", ".join(extra)

    @classmethod
    @docstring_format_args([supported_op_dtypes])
    def constraint_tens_dtype(cls, op):
        "Tensors must be of type: {}"
        valid = True
        extra = []
        tensors = [tens for tens in op.get_ifm_ifm2_weights_ofm() if tens]
        if not tensors:
            tensors = [tens for tens in op.inputs if tens]
        for tens in tensors:
            if tens.dtype not in cls.supported_op_dtypes:
                valid = False
                extra.append(f"Tensor '{tens.name}' has data type: {tens.dtype}")
        return valid, ", ".join(extra)

    @classmethod
    @docstring_format_args([docstring_supported_int32_tensor_ops])
    def constraint_tens_int32_ops(cls, op):
        "Tensors which are int32 are only valid when op type is: {}"
        valid = True
        extra = []
        tensors = [tens for tens in op.get_ifm_ifm2_weights_ofm() if tens]
        if not tensors:
            tensors = [tens for tens in op.inputs if tens]
        for tens in tensors:
            if (tens.dtype == DataType.int32) and (op.type not in cls.supported_int32_tensor_ops):
                valid = False
                extra.append(tens.name)
        extra = ", ".join(extra)
        return valid, f"Op has int32 tensor(s): {extra}"

    @classmethod
    @docstring_format_args(tens_dim_range)
    def constraint_tens_dimension(cls, op):
        "Tensor dimensions must be in the range [{}, {}]"
        tens_min, tens_max = cls.tens_dim_range
        valid = True
        extra = []
        tensors = [tens for tens in op.get_ifm_ifm2_weights_ofm() if tens]
        if not tensors:
            tensors = [tens for tens in op.inputs if tens]
        for tens in tensors:
            if not all(tens_min <= dim <= tens_max for dim in tens.shape):
                valid = False
                extra.append(f"Tensor '{tens.name}' has shape: {tens.shape}")
        return valid, ", ".join(extra)

    @staticmethod
    def constraint_tens_quant_none_check(op):
        "Input(s), Output and Weight tensors must have quantization parameters"
        valid = True
        extra = []
        tensors = [tens for tens in op.get_ifm_ifm2_weights_ofm() if tens]
        for tens in tensors:
            if tens.quantization is None:
                valid = False
                extra.append(tens.name)
        extra = ", ".join(extra)
        return valid, f"Op has tensors with missing quantization parameters: {extra}"

    @staticmethod
    def constraint_tens_quant_scale(op):
        "Input(s), Output and Weight tensors with quantization scales must be finite"
        valid = True
        extra = []
        tensors = [tens for tens in op.get_ifm_ifm2_weights_ofm() if tens]
        for tens in tensors:
            if (tens.quantization.scale_f32 is not None) and np.isinf(tens.quantization.scale_f32).any():
                valid = False
                extra.append(f"Tensor '{tens.name}' has quantization scale: {tens.quantization.scale_f32}")
        return valid, ", ".join(extra)

    @classmethod
    @docstring_format_args([docstring_per_axis_quant_ops])
    def constraint_tens_quant_per_axis(cls, op):
        "Per-axis quantization is only supported for the following op types: {}"
        valid = True
        extra = []
        if op.type not in cls.per_axis_quant_ops:
            tensors = [tens for tens in op.get_ifm_ifm2_weights_ofm() if tens]
            for tens in tensors:
                if tens.quantization.is_per_axis():
                    valid = False
                    extra.append(tens.name)
        return valid, "The following tensor(s) have per-axis quantization parameters: " + ", ".join(extra)

    @classmethod
    @docstring_format_args([docstring_supported_fused_activations])
    def constraint_faf(cls, op):
        "The fused activation function (if present) must be one of type: {}"
        if op.activation is None:
            res = True, "Op has no fused activation function"
        else:
            faf = op.activation.op_type
            valid = faf in cls.supported_fused_activations
            res = valid, f"Op has its fused activation function as: {faf}"
        return res

    @staticmethod
    def constraint_stride_type(op):
        "Stride values for both width and height must be integer types"
        w, h = op.get_kernel_stride()
        valid = is_integer(w) and is_integer(h)
        return valid, f"Op has stride WxH as: {repr(w)}x{repr(h)}"

    @classmethod
    @docstring_format_args(stride_range)
    def constraint_stride_range(cls, op):
        "Stride values for both width and height must be in the range [{}, {}]"
        w, h = op.get_kernel_stride()
        stride_min, stride_max = cls.stride_range
        valid = (stride_min <= w <= stride_max) and (stride_min <= h <= stride_max)
        return valid, f"Op has stride WxH as: {w}x{h}"

    @staticmethod
    def constraint_dilation_type(op):
        "Dilation factor values for both width and height must be integer types"
        w, h = op.get_kernel_dilation()
        valid = is_integer(w) and is_integer(h)
        return valid, f"Op has dilation factor WxH as: {repr(w)}x{repr(h)}"

    @classmethod
    @docstring_format_args(dilation_range)
    def constraint_dilation_range(cls, op):
        "Dilation factor values for both width and height must be in the range [{}, {}]"
        w, h = op.get_kernel_dilation()
        dilation_min, dilation_max = cls.dilation_range
        valid = (dilation_min <= w <= dilation_max) and (dilation_min <= h <= dilation_max)
        return valid, f"Op has dilation factor WxH as: {w}x{h}"

    @classmethod
    @docstring_format_args(dilated_height_range)
    def constraint_dilated_height_range(cls, op):
        "Dilated kernel height must be in the range [{}, {}]"
        h = op.kernel.area_height()
        dilated_height_min, dilated_height_max = cls.dilated_height_range
        valid = dilated_height_min <= h <= dilated_height_max
        return valid, f"Op has dilated kernel height as: {h}"

    @classmethod
    @docstring_format_args(dilated_product_range)
    def constraint_dilated_product_range(cls, op):
        "Product of dilated kernel width and height must be in the range [{}, {}]"
        product = op.kernel.area_width() * op.kernel.area_height()
        dilated_product_min, dilated_product_max = cls.dilated_product_range
        valid = dilated_product_min <= product <= dilated_product_max
        return valid, f"Op has product of dilated kernel width and height as: {product}"

    @staticmethod
    def constraint_weights_type(op):
        "Weight tensor must be 8-bit"
        weights = op.weights
        valid = weights.element_size() == 1
        return valid, f"Tensor '{weights.name}' is {int(weights.element_size() * 8)}-bit"

    @staticmethod
    def constraint_weights_const(op):
        "Weight tensor must be constant"
        weights = op.weights
        valid = weights.values is not None
        return valid, f"Tensor '{weights.name}' has non-constant values"

    @classmethod
    @docstring_format_args([weights_limit])
    def constraint_weights_limit(cls, op):
        "The sum of the weights cannot exceed {}"
        weights = op.weights
        values = weights.quant_values.astype(np.int64) - weights.quantization.zero_point
        limit = np.amax(np.sum(np.absolute(values), axis=(0, 1, 2)))
        valid = limit <= cls.weights_limit
        return valid, f"Tensor '{weights.name}' has the sum of weights: {limit}"

    @classmethod
    @docstring_format_args([supported_bias_dtypes])
    def constraint_bias_type(cls, op):
        "Optional Bias tensor must be of type: {}"
        bias = op.bias
        if bias:
            valid = bias.dtype in cls.supported_bias_dtypes
            return valid, f"Tensor '{bias.name}' has data type: {bias.dtype}"
        return True, "Op has no bias tensor"

    @staticmethod
    def constraint_bias_40bit(op):
        "Optional Bias tensor values must fit within 40-bits"
        bias = op.bias
        if bias and bias.dtype == DataType.int64 and bias.quant_values is not None:
            valid = all(len(bin(quant_value)[2:]) <= 40 for quant_value in bias.quant_values)
            return valid, f"Tensor '{bias.name}' has values larger than 40-bits"
        return True, "Op has no bias tensor, or it fits in 40-bit"

    @staticmethod
    def constraint_batch_size(op):
        "IFM Tensor batch size must be 1"
        ifm = op.ifm
        valid = ifm.shape[0] == 1
        return valid, f"Tensor '{ifm.name}' has batch size: {ifm.shape[0]}"

    @staticmethod
    def constraint_quant_scale_inf(op):
        "The IFM quantization scale divided by the OFM quantization scale must not be infinite"
        ifm_scale = op.ifm.quantization.scale_f32
        ofm_scale = op.ofm.quantization.scale_f32
        valid = not np.isinf(ifm_scale / ofm_scale)
        return valid, f"Op has infinite quantization scale. ifm_scale={ifm_scale} ofm_scale={ofm_scale}"

    @staticmethod
    def constraint_depth_multiplier(op):
        "For depth multipliers > 1, IFM channels must be 1 and OFM channels must be equal to the depth multiplier"
        depth_multiplier = op.attrs.get("depth_multiplier", 1)
        if depth_multiplier > 1:
            ifm_channels = op.ifm.shape[3]
            ofm_channels = op.ofm.shape[3]
            valid = (ifm_channels == 1) and (ofm_channels == depth_multiplier)
            extra = (
                f"Op has ifm_channels={ifm_channels}, ofm_channels={ofm_channels}"
                f" and depth_multiplier={depth_multiplier}"
            )
            return valid, extra
        return True, "Op has depth_multiplier=1"

    @staticmethod
    def constraint_tconv_stride(op):
        "Stride values for both width and height must be 2"
        w = op.kernel.stride.x
        h = op.kernel.stride.y
        valid = (w == 2) and (h == 2)
        return valid, f"Op has stride WxH as: {w}x{h}"

    @staticmethod
    def constraint_tconv_same(op):
        "SAME padding: OFM dimensions must equal IFM dimensions multiplied by stride"
        if op.attrs["padding"] == b"SAME":
            w = op.kernel.stride.x
            h = op.kernel.stride.y
            ifm_shape = op.ifm.shape
            ofm_shape = op.ofm.shape
            valid = (ofm_shape[1] == (ifm_shape[1] * h)) and (ofm_shape[2] == (ifm_shape[2] * w))
            return valid, f"Op has ifm_shape={ifm_shape}, ofm_shape={ofm_shape} and stride WxH as {w}x{h}"
        return True, "Op has padding=VALID"

    @staticmethod
    def constraint_tconv_valid(op):
        """VALID padding: OFM dimensions must equal IFM dimensions multiplied by stride,
                  minus difference between kernel size and stride"""
        if op.attrs["padding"] == b"VALID":
            s_w = op.kernel.stride.x
            s_h = op.kernel.stride.y
            k_w = op.kernel.width
            k_h = op.kernel.height
            ifm_shape = op.ifm.shape
            ofm_shape = op.ofm.shape
            height_check = ofm_shape[1] == (ifm_shape[1] * s_h + max(k_h - s_h, 0))
            width_check = ofm_shape[2] == (ifm_shape[2] * s_w + max(k_w - s_w, 0))
            valid = height_check and width_check
            extra = (
                f"Op has ifm_shape={ifm_shape}, ofm_shape={ofm_shape},"
                f" stride WxH as {s_w}x{s_h} and kernel WxH as {k_w}x{k_h}"
            )
            return valid, extra
        return True, "Op has padding=SAME"

    @staticmethod
    def constraint_matching_in_out_types(op):
        "IFM and OFM data types must match"
        ifm_dtype = op.ifm.dtype
        ofm_dtype = op.ofm.dtype
        valid = ifm_dtype == ofm_dtype
        return valid, f"Op has ifm_dtype={ifm_dtype} and ofm_dtype={ofm_dtype}"

    @staticmethod
    def constraint_beta_value_range(op):
        "Beta value needs to be positive"
        beta = op.attrs.get("beta", 1.0)
        valid = beta >= 0
        return valid, f"Op has beta={beta}"

    @staticmethod
    def constraint_filter_type(op):
        "Kernel filter values for both width and height must be integer types"
        w = op.kernel.width
        h = op.kernel.height
        valid = is_integer(w) and is_integer(h)
        return valid, f"Op has kernel filter WxH as: {repr(w)}x{repr(h)}"

    @classmethod
    @docstring_format_args(filter_range)
    def constraint_filter_range(cls, op):
        "Kernel filter values for both width and height must be in the range [{}, {}]"
        if op.attrs["padding"] == b"SAME":
            w = op.kernel.width
            h = op.kernel.height
            filter_min, filter_max = cls.filter_range
            valid = (filter_min <= w <= filter_max) and (filter_min <= h <= filter_max)
            return valid, f"Op has kernel filter WxH as: {w}x{h}"
        return True, "Op has padding=VALID"

    @classmethod
    @docstring_format_args(filter_height_range)
    def constraint_filter_height_range(cls, op):
        "Kernel filter height must be in the range [{}, {}]"
        h = op.kernel.height
        filter_height_min, filter_height_max = cls.filter_height_range
        valid = filter_height_min <= h <= filter_height_max
        return valid, f"Op has kernel filter height as: {h}"

    @classmethod
    @docstring_format_args(filter_product_range)
    def constraint_filter_product_range(cls, op):
        "Product of kernel filter width and height must be in the range [{}, {}]"
        product = op.kernel.elements_wh()
        filter_product_min, filter_product_max = cls.filter_product_range
        valid = filter_product_min <= product <= filter_product_max
        return valid, f"Op has product of kernel filter width and height as: {product}"

    @staticmethod
    @docstring_format_args(filter_height_range)
    def constraint_filter_height_range_valid_pad(op):
        "VALID padding: Kernel filter height must be in the range [{}, {}]"
        if op.attrs["padding"] == b"VALID":
            return SupportedOperators.constraint_filter_height_range(op)
        return True, "Op has padding=SAME"

    @staticmethod
    @docstring_format_args(filter_product_range)
    def constraint_filter_product_range_valid_pad(op):
        "VALID padding: Product of kernel filter width and height must be in the range [{}, {}]"
        if op.attrs["padding"] == b"VALID":
            return SupportedOperators.constraint_filter_product_range(op)
        return True, "Op has padding=SAME"

    @staticmethod
    def constraint_resize(op):
        """The width and height of the IFM and OFM must match one of the following criteria:
        IFM W and H must both be 1
        IFM must match OFM
        OFM W and H must be 2x IFM -1, if align_corners is True
        OFM W and H must be 2x IFM, if align_corners is False"""
        # Easier to start with False condition as very few cases result in a supported resize
        valid = False
        ifm_shape = op.ifm.shape
        ofm_shape = op.ofm.shape
        align_corners = op.attrs.get("align_corners", False)
        if len(ifm_shape) == 4:
            # Valid if IFM W and H are both 1, or IFM and OFM shape are the same
            if ((ifm_shape[1] == 1) and (ifm_shape[2] == 1)) or (ifm_shape == ofm_shape):
                valid = True
            else:
                upscaled_shape = np.array(ifm_shape[1:3])
                out_shape = np.array(ofm_shape[1:3])
                while (upscaled_shape < out_shape).all():
                    upscaled_shape *= 2
                    if align_corners:
                        upscaled_shape -= 1
                    # Valid if OFM is 2x IFM (-1 for align corners)
                    if np.array_equal(out_shape, upscaled_shape):
                        valid = True
                        break
        return valid, f"Op has ifm_shape={ifm_shape}, ofm_shape={ofm_shape} and align_corners={align_corners}"

    @staticmethod
    def constraint_matching_shapes(op):
        "IFM and OFM shapes must match"
        ifm_shape = op.ifm.shape
        ofm_shape = op.ofm.shape
        valid = ifm_shape == ofm_shape
        return valid, f"Op has ifm_shape={ifm_shape} and ofm_shape={ofm_shape}"

    @staticmethod
    def constraint_splitv_inferred(op):
        "Only one size is allowed to be inferred"
        sizes = op.ifm2.values
        valid = np.count_nonzero(sizes == -1) <= 1
        return valid, f"Op has multiple inferred sizes (-1): {sizes}"

    @staticmethod
    def constraint_axis_exists(op):
        "Axis attribute must exist"
        axis = op.attrs.get("axis")
        valid = axis is not None
        return valid, f"Op has axis={axis}"

    @staticmethod
    def constraint_axis_valid(op):
        "Axis attribute must be in the range [0, <ofm_dimensions>)"
        dims = len(op.ofm.shape)
        axis = op.attrs["axis"]
        axis += dims if axis < 0 else 0
        valid = 0 <= axis < dims
        return valid, f"Op has ofm_dimensions={dims} and axis attribute is: {axis}"

    @staticmethod
    def constraint_matching_dimensionality(op):
        "All Input dimensionalities must match OFM dimensionality"
        valid = True
        extra = []
        ofm_dim = len(op.ofm.shape)
        tensors = [tens for tens in op.inputs if tens]
        for tens in tensors:
            dim = len(tens.shape)
            if dim != ofm_dim:
                valid = False
                extra.append(f"Tensor '{tens.name}' has dimension: {dim}")
        extra = ", ".join(extra)
        return valid, f"Op has ofm_dimension={ofm_dim} and the list of mismatching inputs are: {extra}"

    @staticmethod
    def constraint_valid_dimensions(op):
        "All Input dimensions must match OFM dimension in all axes except the one defined by the axis attribute"
        valid = True
        extra = []
        ofm_shape = op.ofm.shape
        ofm_dim = len(ofm_shape)
        axis = op.attrs["axis"]
        axis += ofm_dim if axis < 0 else 0
        tensors = [tens for tens in op.inputs if tens]
        for tens in tensors:
            if any(tens.shape[dim] != ofm_shape[dim] for dim in range(ofm_dim) if dim != axis):
                valid = False
                extra.append(f"Tensor '{tens.name}' has shape: {tens.shape}")
        extra = ", ".join(extra)
        return valid, f"Op has axis={axis}, ofm_shape={ofm_shape} and the list of mismatching inputs are: {extra}"

    @staticmethod
    def constraint_stridedslice_input_count(op):
        "Exactly 4 Input tensors are required"
        inputs = len(op.inputs)
        valid = inputs == 4
        return valid, f"Op has {inputs} inputs"

    @staticmethod
    def constraint_stridedslice_inputs_const(op):
        "Begin, End and Stride Input tensors must be constant"
        valid = True
        extra = []
        _, begin, end, strides = op.inputs
        if begin.values is None:
            valid = False
            extra.append(f"Begin tensor '{begin.name}'")
        if end.values is None:
            valid = False
            extra.append(f"End tensor '{end.name}'")
        if strides.values is None:
            valid = False
            extra.append(f"Stride tensor '{strides.name}'")
        extra = ", ".join(extra)
        return valid, f"Op has non-constant tensors: {extra}"

    @staticmethod
    def constraint_stridedslice_stride_values(op):
        "All Strides values must be 1"
        strides = op.inputs[3]
        valid = all(stride == 1 for stride in strides.values)
        return valid, f"Op has strides values {strides.values}"

    @staticmethod
    def constraint_ellipsis_mask(op):
        "ellipsis_mask must be 0"
        ellipsis = op.attrs["ellipsis_mask"]
        valid = ellipsis == 0
        return valid, f"Op has ellipsis mask as: {ellipsis}"

    @staticmethod
    def constraint_axis_masks(op):
        "new_axis_mask and shrink_axis_mask cannot both be set"
        new_axis = op.attrs["new_axis_mask"]
        shrink_axis = op.attrs["shrink_axis_mask"]
        valid = (new_axis == 0) or (shrink_axis == 0)
        return valid, f"Op has new_axis_mask={new_axis} and shrink_axis_mask={shrink_axis}"

    @staticmethod
    def constraint_slice_ranges(op):
        "Slice 'end' values must be greater than 'begin' values"
        ifm, begin, end, _ = op.inputs
        # Calculate offset begin/end
        offset_begin = get_slice_offsets(ifm.shape, begin, op.attrs["begin_mask"], is_begin=True)
        offset_end = get_slice_offsets(ifm.shape, end, op.attrs["end_mask"], is_begin=False)
        # Check "end - begin" doesn't result in any zero or negative elements
        valid = all((e - b) > 0 for b, e in zip(offset_begin, offset_end))
        return valid, f"Op has begin_values={begin.values} and end_values={end.values}"

    @staticmethod
    def constraint_matching_inputs_types(op):
        "Both Input data types must match"
        ifm_dtype = op.ifm.dtype
        ifm2_dtype = op.ifm2.dtype
        valid = ifm_dtype == ifm2_dtype
        return valid, f"Op has ifm_dtype={ifm_dtype} and ifm2_dtype={ifm2_dtype}"

    @staticmethod
    def constraint_matching_signed(op):
        "For IFM that are signed, OFM must also be signed"
        valid = True
        ifm_dtype = op.ifm.dtype
        ofm_dtype = op.ofm.dtype
        if ifm_dtype.type & BaseType.Signed:
            valid = bool(ofm_dtype.type & BaseType.Signed)
        return valid, f"Op has ifm_dtype={ifm_dtype} and ofm_dtype={ofm_dtype}"

    @staticmethod
    def constraint_unsigned_valid(op):
        "For IFM that are unsigned, OFM must either be the same type or int32"
        valid = True
        ifm_dtype = op.ifm.dtype
        ofm_dtype = op.ofm.dtype
        if ifm_dtype.type & BaseType.Unsigned:
            valid = (ifm_dtype == ofm_dtype) or (ofm_dtype == DataType.int32)
        return valid, f"Op has ifm_dtype={ifm_dtype} and ofm_dtype={ofm_dtype}"

    @staticmethod
    def constraint_inputs_int32(op):
        "Both Input data types must be int32"
        ifm_dtype = op.ifm.dtype
        ifm2_dtype = op.ifm2.dtype
        valid = (ifm_dtype == DataType.int32) and (ifm2_dtype == DataType.int32)
        return valid, f"Op has ifm_dtype={ifm_dtype} and ifm2_dtype={ifm2_dtype}"

    @staticmethod
    def constraint_output_int32(op):
        "OFM must be int32"
        ofm_dtype = op.ofm.dtype
        valid = ofm_dtype == DataType.int32
        return valid, f"Op has ofm_dtype={ofm_dtype}"

    @staticmethod
    def constraint_matching_quantization_parameters(op):
        "Both Input quantization parameters must match OFM quantization parameters"
        valid = True
        extra = []
        if not check_quantized_tens_scaling_equal(op.ofm, op.ifm):
            valid = False
            extra.append(op.ifm.name)
        if not check_quantized_tens_scaling_equal(op.ofm, op.ifm2):
            valid = False
            extra.append(op.ifm2.name)
        extra = ", ".join(extra)
        return valid, f"Op has tensors with different quantization parameters to the OFM '{op.ofm.name}': {extra}"

    @staticmethod
    def constraint_elemwise_batch_size(op):
        "Batch size must be 1 for Input tensors with more than 2 dimensions"
        valid = True
        extra = []
        for tens in (op.ifm, op.ifm2):
            # Unary ops have ifm2 as None
            if tens is not None:
                if (len(tens.shape) > 2) and (tens.shape[0] != 1):
                    valid = False
                    extra.append(tens.name)
        extra = ", ".join(extra)
        return valid, f"Op has invalid input tensors: {extra}"

    @staticmethod
    def constraint_matching_either_shapes(op):
        "At least one Input's shape must match the OFM's shape"
        ifm_shape = op.ifm.shape
        ifm2_shape = op.ifm2.shape if op.ifm2 else None
        ofm_shape = op.ofm.shape
        valid = (ifm_shape == ofm_shape) or (ifm2_shape == ofm_shape)
        return valid, f"Op has ifm_shape={ifm_shape}, ifm2_shape={ifm2_shape} and ofm_shape={ofm_shape}"

    @staticmethod
    def constraint_broadcast_shapes(op):
        "Broadcasting is only allowed for rank indices with dimension 1, from either IFM1 or IFM2"
        ifm_shape = op.ifm.shape
        ifm2_shape = op.ifm2.shape if op.ifm2 else None
        ofm_shape = op.ofm.shape
        valid = True
        if ifm_shape is not None and ifm2_shape is not None:
            # align trailing dimensions
            size = min(len(ifm_shape), len(ifm2_shape))
            for i, i2, o in zip(ifm_shape[-size:], ifm2_shape[-size:], ofm_shape[-size:]):
                mi = max(i, i2)
                # Input dimensions should match or one should be of dimension 1
                # Output dimension should match the largest input dimension, together
                # with constraint_match_either_shapes ensures broadcast from only one input
                if not (i == i2 or i == 1 or i2 == 1) or o != mi:
                    valid = False
                    break

        return valid, f"Op has ifm_shape={ifm_shape} and ifm2_shape={ifm2_shape}"

    @staticmethod
    def constraint_alpha_valid(op):
        "Alpha must not be negative"
        alpha = op.attrs["alpha"]
        valid = alpha >= 0
        return valid, f"Op has alpha={alpha}"
