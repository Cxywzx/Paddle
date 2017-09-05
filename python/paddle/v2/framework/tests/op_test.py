import unittest
import numpy as np
import itertools
import paddle.v2.framework.core as core
from paddle.v2.framework.op import Operator


def create_op(scope, op_type, inputs, outputs, attrs):
    kwargs = dict()

    for ins in Operator.get_op_inputs(op_type):
        in_name = ins[0]
        in_dup = ins[1]
        if in_name in inputs:
            kwargs[in_name] = []
            if in_dup:
                sub_in = inputs[in_name]
                for sub_in_name in sub_in:
                    var = scope.new_var(sub_in_name)
                    tensor = var.get_tensor()
                    kwargs[in_name].append(sub_in_name)
            else:
                var = scope.new_var(in_name)
                tensor = var.get_tensor()
                kwargs[in_name].append(in_name)

    for outs in Operator.get_op_outputs(op_type):
        out_name = outs[0]
        out_dup = outs[1]
        if out_name in outputs:
            kwargs[out_name] = []
            if out_dup:
                sub_in = outputs[out_name]
                for sun_in_name in sub_in:
                    var = scope.new_var(sun_in_name)
                    tensor = var.get_tensor()
                    kwargs[out_name].append(sun_in_name)
            else:
                var = scope.new_var(out_name)
                tensor = var.get_tensor()
                kwargs[out_name].append(out_name)

    for attr_name in Operator.get_op_attr_names(op_type):
        kwargs[attr_name] = attrs[attr_name]
    return Operator(op_type, **kwargs)


def set_input(scope, op, inputs, place):
    for ins in Operator.get_op_inputs(op.type()):
        in_name = ins[0]
        in_dup = ins[1]
        if in_name in inputs:
            kwargs[in_name] = []
            if in_dup:
                sub_in = inputs[in_name]
                for sub_in_name in sub_in:
                    var = scope.find_var(sub_in_name)
                    tensor = var.get_tensor()
                    arr = sub_in[sub_in_name]
                    tensor.set_dims(arr.shape)
                    tensor.set(arr, place)
            else:
                var = scope.find_var(in_name)
                tensor = var.get_tensor()
                arr = self.inputs[in_name]
                tensor.set_dims(arr.shape)
                tensor.set(arr, place)


def get_numeric_gradient(scope,
                         op,
                         inputs,
                         input_to_check,
                         output_name,
                         delta=0.005,
                         in_place=False):

    set_input(op, inputs, core.CPUPlace())
    op.infer_shape(scope)

    tensor_to_check = scope.find_var(input_to_check).get_tensor()

    def product(dim):
        return reduce(lambda a, b: a * b, dim, 1)

    ctx = core.DeviceContext.create(place)

    def get_output():
        op.run(scope, ctx)
        return numpy.array(scope.find_var(output_name).get_tensor()).sum()

    tensor_to_check = scope.find_var(input_to_check).get_tensor()
    tensor_size = product(tensor_to_check.get_dims())
    gradient_flat = numpy.zeros(shape=(tensor_size, ), dtype='float32')
    # we only compute gradient of one element each time.
    # we use a for loop to compute the gradient of every element.
    for i in xrange(tensor_size):
        if in_place:
            set_input(op, inputs, core.CPUPlace())

        # get one input element throw it's index i.
        origin = tensor_to_check.get_float_element(i)
        # add delta to it, run op and then get the sum of the result tensor.
        x_pos = origin + delta
        tensor_to_check.set_float_element(i, x_pos)
        y_pos = get_output(op, outputs, output_name, core.CPUPlace())

        if in_place:
            set_input(op, inputs, core.CPUPlace())

        x_neg = origin - delta
        tensor_to_check.set_float_element(i, x_neg)
        y_neg = get_output(op, outputs, output_name, core.CPUPlace())

        tensor_to_check.set_float_element(i, origin)
        gradient_flat[i] = (y_pos - y_neg) / delta / 2

    return gradient_flat.reshape()


def get_backward_op(scope, op, no_grad_set):
    backward_op = core.Operator.backward(op, no_grad_set)
    for input in backward_op.inputs()["all"]:
        var = scope.new_var(input)
        var.get_tensor()
    for output in backward_op.outputs()["all"]:
        var = scope.new_var(output)
        var.get_tensor()
    return backward_op


def get_gradient(op, inputs, grad_name, place, no_grad_set=None):
    ctx = core.DeviceContext.create(place)
    set_input(op, inputs, place)

    op.infer_shape(scope)
    op.run(scope, ctx)

    if no_grad_set is None:
        no_grad_set = set()

    backward_op = get_backward_op(op, no_grad_set)

    for input in backward_op.inputs()["all"]:
        grad_var = scope.find_var(input)
        grad_tensor = var.get_tensor()

        var = scope.find_var(remove_grad_var_name(input))
        tensor = var.get_tensor()

        grad_tensor.set_dims(tensor.shape())
        data = numpy.ones(out_tensor.shape(), dtype=numpy.float32)
    grad_tensor.set(data, place)

    backward_op.infer_shape(scope)
    backward_op.run(scope, ctx)

    out = numpy.array(find_var(grad_name).get_tensor())
    return out


def grad_var_name(var_name):
    return var_name + "@GRAD"


def remove_grad_var_name(var_name):
    return var_name[0:-5]


class OpTest(unittest.TestCase):
    def __init__(self, op_type, inputs, outputs, attrs):
        self.op_type = op_type
        self.inputs = inputs
        self.outputs = outputs
        self.attrs = attrs

    def check_output(self, place):
        self.scope = core.Scope()
        self.op = create_op(self.scope, self.op_type, self.inputs, self.outputs,
                            self.attrs)
        if isinstance(place, core.GPUPlace) and not op.support_gpu():
            return
        set_input(self.scope, self.op, self.inputs, place)
        op.infer_shape(scope)
        ctx = core.DeviceContext.create(place)
        op.run(scope, ctx)

        for outs in Operator.get_op_outputs(op.type()):
            out_name = outs[0]
            out_dup = outs[1]
            if out_dup:
                sub_out = self.outputs[out_name]
                for sub_out_name in sub_out:
                    actual = np.array(
                        self.scope.find_var(sub_out_name).get_tensor())
                    expect = sub_out[sub_out_name]
                    self.assertTrue(
                        np.allclose(
                            actual, expect, atol=1e-05),
                        "output name: " + out_name + "has diff")
            else:
                actual = np.array(self.scope.find_var(out_name).get_tensor())
                expect = self.outputs[out_name]
                self.assertTrue(
                    numpy.allclose(
                        actual, expect, atol=1e-05),
                    "output name: " + out_name + "has diff")

        def check_grad(self,
                       input_to_checl,
                       output_name,
                       no_grad_set=None,
                       in_place=False):
            self.scope = core.Scope()

        self.op = create_op(self.scope, self.op_type, self.inputs, self.outputs,
                            self.attrs)

        if no_grad_set is None:
            no_grad_set = set()

        numeric_grad = get_numeric_gradient(
            self.scope,
            self.op,
            self.inputs,
            input_to_check,
            output_name,
            in_place=in_place)

        grad_name = grad_var_name(input_to_check)

        places = [core.CPUPlace()]
        if core.is_compile_gpu() and op.support_gpu():
            places.append(core.GPUPlace(0))

        for place in places:
            analytic_grads = get_gradient(self.scope, self.op, self.inputs,
                                          grad_name, place, no_grad_set)

        self.assertTrue(np.allclose(numeric_grad, analytic_grads))
