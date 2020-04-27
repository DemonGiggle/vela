# automatically generated by the FlatBuffers compiler, do not modify

# namespace: tflite

import flatbuffers

class DepthwiseConv2DOptions(object):
    __slots__ = ['_tab']

    @classmethod
    def GetRootAsDepthwiseConv2DOptions(cls, buf, offset):
        n = flatbuffers.encode.Get(flatbuffers.packer.uoffset, buf, offset)
        x = DepthwiseConv2DOptions()
        x.Init(buf, n + offset)
        return x

    # DepthwiseConv2DOptions
    def Init(self, buf, pos):
        self._tab = flatbuffers.table.Table(buf, pos)

    # DepthwiseConv2DOptions
    def Padding(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(4))
        if o != 0:
            return self._tab.Get(flatbuffers.number_types.Int8Flags, o + self._tab.Pos)
        return 0

    # DepthwiseConv2DOptions
    def StrideW(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(6))
        if o != 0:
            return self._tab.Get(flatbuffers.number_types.Int32Flags, o + self._tab.Pos)
        return 0

    # DepthwiseConv2DOptions
    def StrideH(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(8))
        if o != 0:
            return self._tab.Get(flatbuffers.number_types.Int32Flags, o + self._tab.Pos)
        return 0

    # DepthwiseConv2DOptions
    def DepthMultiplier(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(10))
        if o != 0:
            return self._tab.Get(flatbuffers.number_types.Int32Flags, o + self._tab.Pos)
        return 0

    # DepthwiseConv2DOptions
    def FusedActivationFunction(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(12))
        if o != 0:
            return self._tab.Get(flatbuffers.number_types.Int8Flags, o + self._tab.Pos)
        return 0

    # DepthwiseConv2DOptions
    def DilationWFactor(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(14))
        if o != 0:
            return self._tab.Get(flatbuffers.number_types.Int32Flags, o + self._tab.Pos)
        return 1

    # DepthwiseConv2DOptions
    def DilationHFactor(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(16))
        if o != 0:
            return self._tab.Get(flatbuffers.number_types.Int32Flags, o + self._tab.Pos)
        return 1

def DepthwiseConv2DOptionsStart(builder): builder.StartObject(7)
def DepthwiseConv2DOptionsAddPadding(builder, padding): builder.PrependInt8Slot(0, padding, 0)
def DepthwiseConv2DOptionsAddStrideW(builder, strideW): builder.PrependInt32Slot(1, strideW, 0)
def DepthwiseConv2DOptionsAddStrideH(builder, strideH): builder.PrependInt32Slot(2, strideH, 0)
def DepthwiseConv2DOptionsAddDepthMultiplier(builder, depthMultiplier): builder.PrependInt32Slot(3, depthMultiplier, 0)
def DepthwiseConv2DOptionsAddFusedActivationFunction(builder, fusedActivationFunction): builder.PrependInt8Slot(4, fusedActivationFunction, 0)
def DepthwiseConv2DOptionsAddDilationWFactor(builder, dilationWFactor): builder.PrependInt32Slot(5, dilationWFactor, 1)
def DepthwiseConv2DOptionsAddDilationHFactor(builder, dilationHFactor): builder.PrependInt32Slot(6, dilationHFactor, 1)
def DepthwiseConv2DOptionsEnd(builder): return builder.EndObject()
