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
# Contains unit tests for encode_weights API for an external consumer
import numpy as np
import pytest

from ethosu.vela import weight_compressor
from ethosu.vela.api import NpuBlockTraversal
from ethosu.vela.architecture_features import Accelerator


@pytest.mark.parametrize(
    "arch",
    [
        Accelerator.Ethos_U55_32,
        Accelerator.Ethos_U55_64,
        Accelerator.Ethos_U55_128,
        Accelerator.Ethos_U55_256,
        Accelerator.Yoda_256,
        Accelerator.Yoda_512,
    ],
)
@pytest.mark.parametrize("dilation_x", [1, 2])
@pytest.mark.parametrize("dilation_y", [1, 2])
@pytest.mark.parametrize("ifm_bitdepth", [8, 16])
@pytest.mark.parametrize("depth_control", [1, 2, 3])
@pytest.mark.parametrize("weights_shape_and_block_depth", [((16, 16, 16, 16), 8), ((3, 3, 25, 16), 8)])
def test_encode_weights(
    arch, weights_shape_and_block_depth, dilation_x, dilation_y, ifm_bitdepth, depth_control,
):
    """
    This unit test checks the interface of the API function but not the functionality.
    Functional correctness is tested at a system level.
    """

    weights_shape = weights_shape_and_block_depth[0]
    ofm_block_depth = weights_shape_and_block_depth[1]
    val_max = np.iinfo(np.uint8).max
    weights_hwio = np.random.randint(val_max, size=weights_shape, dtype=np.uint8)
    weights_ohwi = np.transpose(weights_hwio, (3, 0, 1, 2))
    is_depthwise = True if depth_control == 2 else False
    block_traversal = NpuBlockTraversal.PART_KERNEL_FIRST if depth_control == 3 else NpuBlockTraversal.DEPTH_FIRST
    dilation_xy = (dilation_x, dilation_y)

    encoded_stream = weight_compressor.encode_weights(
        accelerator=arch,
        weights_volume=weights_ohwi,
        dilation_xy=dilation_xy,
        ifm_bitdepth=ifm_bitdepth,
        ofm_block_depth=ofm_block_depth,
        is_depthwise=is_depthwise,
        block_traversal=block_traversal,
    )
    assert type(encoded_stream) == bytearray
