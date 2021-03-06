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
#
# Description:
# Contains external APIs
from enum import auto
from enum import Enum
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import Tuple

import numpy

API_version_major = 1
API_version_minor = 0
api_version = f"{API_version_major}.{API_version_minor}"


class NpuAccelerator(Enum):
    """
    Supported accelerators
    """

    Ethos_U55_32 = auto()
    Ethos_U55_64 = auto()
    Ethos_U55_128 = auto()
    Ethos_U55_256 = auto()
    Ethos_U65_256 = auto()
    Ethos_U65_512 = auto()


class NpuElementWiseOp(Enum):
    """
    Elementwise operation
    """

    ADD = auto()
    SUB = auto()
    MUL = auto()
    ABS = auto()
    MIN = auto()
    MAX = auto()
    LRELU = auto()  # Leaky relu
    CLZ = auto()  # Number leading zeros
    SHR = auto()  # Rounded right-shift
    SHL = auto()  # Bitwise shift-left


class NpuPoolingOp(Enum):
    """
    Pooling operation
    """

    MAX = auto()
    AVERAGE = auto()
    REDUCE_SUM = auto()


class NpuActivationOp(Enum):
    """
    Activation function
    """

    NONE_OR_RELU = auto()  # Clamps output using min/max
    TANH = auto()
    SIGMOID = auto()
    TABLE_LOOKUP = auto()  # Performs table look-up, using the provided table lookup index


class NpuRoundingMode(Enum):
    """
    Available rounding modes
    """

    TFL = auto()  # TensorFlow Lite rounding
    TRUNCATE = auto()  # Truncate towards zero
    NATURAL = auto()  # Round to nearest with x.5 rounded up, towards +infinity


class NpuLayout(Enum):
    """
    Tensor layout of feature maps
    """

    NHWC = auto()
    NHCWB16 = auto()

    def __str__(self):
        return self.name


class NpuResamplingMode(Enum):
    """
    Resampling mode
    """

    NONE = auto()  # No resampling is performed
    NEAREST = auto()  # 2x2 insert nearest
    TRANSPOSE = auto()  # 2x2 transpose


class NpuBlockTraversal(Enum):
    """
    Block-traversal of weights
    """

    DEPTH_FIRST = auto()
    PART_KERNEL_FIRST = auto()


class NpuDataType(Enum):
    """
    Supported data types in feature maps
    """

    UINT8 = 8, False, auto()
    INT8 = 8, True, auto()
    UINT16 = 16, False, auto()
    INT16 = 16, True, auto()
    INT32 = 32, True, auto()

    def is_signed(self) -> bool:
        """Checks if this data type is signed or unsigned"""
        return self.value[1]

    def size_in_bits(self) -> int:
        """ Size of the data type in bits"""
        return self.value[0]

    def size_in_bytes(self) -> int:
        """ Size of the data type in bytes"""
        return self.value[0] // 8

    def min_value(self) -> int:
        """Minimum value of this type"""
        if self.is_signed():
            return -(1 << (self.size_in_bits() - 1))
        else:
            return 0

    def max_value(self) -> int:
        """Maximum value of this type"""
        if self.is_signed():
            return (1 << (self.size_in_bits() - 1)) - 1
        else:
            return (1 << self.size_in_bits()) - 1

    def __str__(self):
        return self.name

    __repr__ = __str__


class NpuAddressRange(NamedTuple):
    """
    Address range
    """

    region: int  # Memory region, a value between 0 and 7
    address: int  # Address, offset from the region's base address
    length: int  # The length of the range, in bytes

    def __str__(self):
        return f"(region={self.region}, address={hex(self.address)}, length={self.length})"


class NpuTileBox(NamedTuple):
    """
    Specifies the addresses and dimensions of the tiles of a feature map.
    A feature map can use 1 to 4 tiles
    """

    height_0: int  # The height of tile 0
    height_1: int  # The height of tile 1, 0 if unused
    width_0: int  # the width of tile 0, and tile 2 (if used)
    addresses: List[int]  # A list of 4 addresses, set unused addresses to 0


class NpuShape3D(NamedTuple):
    """
    Shape of (part of) a feature map
    """

    height: int
    width: int
    depth: int


class NpuQuantization(NamedTuple):
    """
    Quantization parameters
    """

    scale_f32: Optional[float]
    zero_point: int


class NpuPadding(NamedTuple):
    """
    Padding to be applied to a convolution operation
    """

    top: int
    left: int
    bottom: int
    right: int


class NpuActivation:
    """
    Activation function, fused with NPU operations
    """

    def __init__(self, op_type: NpuActivationOp):
        self.op_type = op_type  # The activation operation to be performed
        # min/max are optional
        self.min: Optional[float] = None  # E.g. set to 0.0 for RELU
        self.max: Optional[float] = None  # E.g. set to 6.0 for RELU6
        # Table lookup index, only applicable for TABLE_LOOKUP activation, 0-7
        self.lookup_table_index: int = 0


class NpuFeatureMap:
    """
    Basic information about IFM, IFM2, OFM
    """

    def __init__(self):
        self.data_type: NpuDataType = NpuDataType.UINT8
        # The memory region, a value 0-7
        self.region: int = 0
        # Shape of the feature map
        self.shape: NpuShape3D = NpuShape3D(height=0, width=0, depth=0)
        # The tiles that comprise the feature map. In the normal case when only 1 tile is used,
        # height_0 == self.shape.height, height_1 is 0, width_0 == self.shape.width, addresses[1:] are set to 0
        self.tiles: NpuTileBox = NpuTileBox(height_0=0, height_1=0, width_0=0, addresses=[0, 0, 0, 0])
        self.quantization: Optional[NpuQuantization]
        self.layout: NpuLayout = NpuLayout.NHWC
        # x/y/c strides used by the NPU when traversing the feature map, if None, vela will use default strides
        self.strides: Optional[NpuShape3D] = None


class NpuKernel:
    """
    Kernel information for NPU operations
    """

    def __init__(self, w: int, h: int, stride_x: int = 1, stride_y: int = 1, dilation_x: int = 1, dilation_y: int = 1):
        assert stride_x > 0 and stride_y > 0
        assert dilation_x > 0 and dilation_y > 0
        self.width = w
        self.height = h
        self.stride_x = stride_x
        self.stride_y = stride_y
        self.dilation_x = dilation_x
        self.dilation_y = dilation_y


class NpuOperationType(Enum):
    """
    Type of NPU operation
    """

    Dma = auto()
    Conv2D = auto()
    ConvDepthWise = auto()
    Pooling = auto()
    ElementWise = auto()


class NpuOperation:
    """
    Base class for all NPU operations
    """

    def __init__(self, op_type: NpuOperationType):
        self.op_type = op_type


class NpuDmaOperation(NpuOperation):
    """
    DMA operation
    """

    def __init__(self, src: NpuAddressRange, dest: NpuAddressRange):
        super().__init__(NpuOperationType.Dma)
        self.src = src
        self.dest = dest
        # DMA channel, usually 0 (user channel)
        self.channel: int = 0
        # Channel mode, 0 = external, 1 = internal (should usually be 0)
        self.mode: int = 0


class NpuBlockOperation(NpuOperation):
    """
    Base class for operations which produce an OFM
    """

    def __init__(self, op_type: NpuOperationType):
        super().__init__(op_type)
        self.ifm: Optional[NpuFeatureMap] = None
        self.ifm2: Optional[NpuFeatureMap] = None
        # The non-quantized scalar value in a binary elementwise operation. Only set if IFM2 is scalar
        self.ifm2_scalar: Optional[float] = None
        self.ofm: Optional[NpuFeatureMap] = None
        self.kernel: Optional[NpuKernel] = None
        # Weights, one element for each NPU core, empty if no weights are used.
        # Must have been compressed using weight_compressor.encode_weights()
        self.weights: List[NpuAddressRange] = []
        # Biases, one element for each NPU core, empty if no bias is used.
        # Must have been encoded using weight_compressor.encode_bias()
        self.biases: List[NpuAddressRange] = []
        self.padding: Optional[NpuPadding] = None
        # Optional activation function to be applied
        self.activation: Optional[NpuActivation] = None
        # The block config is the unit of work in which the NPU generates the OFM.
        # If the operation has weights, the depth of the block config must be the same as
        # the ofm depth used in the call to weight_compressor.encode_weights()
        # If set to None, vela will determine a suitable block size (can only be used if there are no weights)
        # If block_config.width and height are set to -1, vela will determine suitable width/height
        self.block_config: Optional[NpuShape3D] = None  # OFM_BLK parameters
        self.rounding_mode: NpuRoundingMode = NpuRoundingMode.TFL
        # Set to True if the operations is fused with a Quantize operation (affects scaling)
        self.fused_quantize: bool = False
        # IFM upscaling to be applied
        self.ifm_upscale: NpuResamplingMode = NpuResamplingMode.NONE


class NpuConv2DOperation(NpuBlockOperation):
    """
    NPU_OP_CONV operation
    """

    def __init__(self):
        super().__init__(NpuOperationType.Conv2D)
        # Block traversal must be consistent with the block_traversal parameter specified in
        # weight_compressor.encode_weights()
        self.block_traversal: NpuBlockTraversal = NpuBlockTraversal.PART_KERNEL_FIRST


class NpuConvDepthWiseOperation(NpuBlockOperation):
    """
    NPU_OP_DEPTHWISE operation
    """

    def __init__(self):
        super().__init__(NpuOperationType.ConvDepthWise)


class NpuPoolingOperation(NpuBlockOperation):
    """
    NPU_OP_POOL operation
    """

    def __init__(self, pooling_op_type: NpuPoolingOp):
        super().__init__(NpuOperationType.Pooling)
        self.sub_op_type: NpuPoolingOp = pooling_op_type
        # Set to a float value for ResizeBilinear operations (affects scaling), else to None
        self.rescale: Optional[float] = None


class NpuElementWiseOperation(NpuBlockOperation):
    """
    NPU_OP_ELEMENTWISE operation
    """

    def __init__(self, elementwise_op_type: NpuElementWiseOp):
        super().__init__(NpuOperationType.ElementWise)
        self.sub_op_type: NpuElementWiseOp = elementwise_op_type
        # Set to True for binary operators where IFM2 should be used as first operand
        self.reversed_operands: bool = False
        # Set to a tuple (scale, shift) for explicit rescale, else to None
        self.rescale: Optional[Tuple] = None


def npu_get_API_version():
    """
    Public facing API to get the API version
    :return: int, the 16 most significant bits, corresponding to major version
            the 16 least significant bits, corresponding to minor version
    """
    version = (API_version_major << 16) | (API_version_minor & 0xFFFF)
    return version


def npu_encode_weights(
    accelerator: NpuAccelerator,
    weights_volume: numpy.ndarray,
    dilation_xy: Tuple[int, int],
    ifm_bitdepth: int,
    ofm_block_depth: int,
    is_depthwise: bool,
    block_traversal: NpuBlockTraversal,
):
    """
    Public facing API to use the Ethos-U weight encoding.

    :param accelerator: NpuAccelerator enum to pick the correct accelerator
    :param weights_volume: numpy.ndarray in OHWI layout with a shape of four
    :param dilation_xy: a two element tuple of dilation attributes in x,y dimension
    :param ifm_bitdepth: the bitdepth of input feature map
    :param ofm_block_depth: the depth of blocks for processing
    :param is_depthwise: a boolean indicating these weights are used for a depthwise traversal
    :param block_traversal: indicates how these weights are traversed on sub-kernel basis
    :return: a bytearray of compressed weights
    """
    from .architecture_features import Accelerator
    from . import weight_compressor

    acc = Accelerator.from_npu_accelerator(accelerator)
    return weight_compressor.encode_weights(
        acc, weights_volume, dilation_xy, ifm_bitdepth, ofm_block_depth, is_depthwise, block_traversal
    )


def npu_encode_bias(bias: numpy.int64, scale: int, shift: int):
    """
    Public facing API to pack bias and scale values as required by the hardware
    :param bias: 64-bit signed number that includes 40-bit signed bias
    :param scale: 32-bit scale value
    :param shift: 6-bit shift value
    :return: packed 80-bit [0(2-bits),shift(6-bits),scale(32-bits),bias(40-bits)]
    """
    from . import weight_compressor

    return weight_compressor.encode_bias(bias, scale, shift)


def npu_generate_register_command_stream(npu_op_list: List[NpuOperation], accelerator: NpuAccelerator) -> List[int]:
    """
    Public facing API for generating an Ethos-U register command stream.
    Calculates dependencies between commands and inserts wait operations if needed.

    :param npu_op_list: List[NpuOperation] list of high level NPU operations
    :param accelerator: NpuAccelerator enum to pick the correct accelerator
    :return register commands, as a list of 32-bit integers
    """
    from . import register_command_stream_generator

    return register_command_stream_generator.generate_register_command_stream(npu_op_list, accelerator)


def npu_create_driver_payload(register_command_stream: List[int], accelerator: NpuAccelerator) -> bytes:
    """
    Public facing API for generating driver payload, containing a driver header
    and the given Ethos-U register command stream.
    Returns the payload, in little endian format, which must be placed in memory on a 16-byte aligned
    address.

    :param register_command_stream: List[int] register commands, as a list of 32-bit integers
    :param accelerator: NpuAccelerator enum to pick the correct accelerator
    :return driver payload, as a byte array
    """
    from . import driver_actions

    return driver_actions.npu_create_driver_payload(register_command_stream, accelerator)
