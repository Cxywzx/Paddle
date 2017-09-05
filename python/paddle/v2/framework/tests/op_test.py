import unittest
import numpy as np
import itertools
import paddle.v2.framework.core as core
from paddle.v2.framework.op import Operator


def grad_var_name(var_name):
    return var_name + "@GRAD"


def remove_grad_var_name(var_name):
    return var_name[0:-5]


def create_op(scope, op_type, inputs, outputs, attrs=None):
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

    # for attr_name in Operator.get_op_attr_names(op_type):
    #	  kwargs[attr_name] = attrs[attr_name]
    return Operator(op_type, **kwargs)


def set_input(scope, op, inputs, place):
    for ins in Operator.get_op_inputs(op.type()):
        in_name = ins[0]
        in_dup = ins[1]
        if in_name in inputs:
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
                arr = inputs[in_name]
                tensor.set_dims(arr.shape)
                tensor.set(arr, place)


def set_output_grad(scope, op, outputs, place):
    for outs in Operator.get_op_outputs(op.type()):
        out_name = outs[0]
        out_dup = outs[1]
        if out_name in outputs:
            if out_dup:
                sub_out = outputs[out_name]
                for sub_out_name in sub_out:
                    out_tensor = scope.find_var(sub_out_name).get_tensor()
                    grad_tensor = scope.new_var(grad_var_name(
                        sub_out_name)).get_tensor()
                    grad_tensor.set_dims(out_tensor.shape())
                    data = np.ones(out_tensor.shape(), dtype=np.float32)
                    grad_tensor.set(data, place)
            else:
                out_tensor = scope.find_var(out_name).get_tensor()
                grad_tensor = scope.new_var(grad_var_name(out_name)).get_tensor(
                )
                grad_tensor.set_dims(out_tensor.shape())
                data = np.ones(out_tensor.shape(), dtype=np.float32)
                grad_tensor.set(data, place)


def get_numeric_gradient(scope,
                         op,
                         inputs,
                         input_to_check,
                         output_name,
                         delta=0.0005,
                         in_place=False):

    set_input(scope, op, inputs, core.CPUPlace())
    op.infer_shape(scope)

    tensor_to_check = scope.find_var(input_to_check).get_tensor()

    def product(dim):
        return reduce(lambda a, b: a * b, dim, 1)

    ctx = core.DeviceContext.create(core.CPUPlace())

    def get_output():
        op.run(scope, ctx)
        return np.array(scope.find_var(output_name).get_tensor()).sum()

    tensor_to_check = scope.find_var(input_to_check).get_tensor()
    tensor_size = product(tensor_to_check.get_dims())
    gradient_flat = np.zeros(shape=(tensor_size, ), dtype='float32')
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
        y_pos = get_output()

        if in_place:
            set_input(op, inputs, core.CPUPlace())

        x_neg = origin - delta
        tensor_to_check.set_float_element(i, x_neg)
        y_neg = get_output()

        tensor_to_check.set_float_element(i, origin)
        gradient_flat[i] = (y_pos - y_neg) / delta / 2

    return gradient_flat.reshape(tensor_to_check.get_dims())


def get_backward_op(scope, op, no_grad_set):
    backward_op = core.Operator.backward(op, no_grad_set)
    for input in backward_op.inputs_names():
        var = scope.new_var(input)
        var.get_tensor()
    for output in backward_op.outputs_names():
        var = scope.new_var(output)
        var.get_tensor()
    return backward_op


def get_gradient(scope, op, inputs, outputs, grad_name, place,
                 no_grad_set=None):
    ctx = core.DeviceContext.create(place)
    set_input(scope, op, inputs, place)

    op.infer_shape(scope)
    op.run(scope, ctx)

    if no_grad_set is None:
        no_grad_set = set()

    backward_op = get_backward_op(scope, op, no_grad_set)
    set_output_grad(scope, op, outputs, place)

    backward_op.infer_shape(scope)
    backward_op.run(scope, ctx)

    out = np.array(scope.find_var(grad_name).get_tensor())
    return out


class OpTest(unittest.TestCase):
    def check_output(self, place):
        self.scope = core.Scope()
        self.op = create_op(self.scope, self.op_type, self.inputs, self.outputs)
        if isinstance(place, core.GPUPlace) and not self.op.support_gpu():
            return
        set_input(self.scope, self.op, self.inputs, place)
        self.op.infer_shape(self.scope)
        ctx = core.DeviceContext.create(place)
        self.op.run(self.scope, ctx)

        for outs in Operator.get_op_outputs(self.op.type()):
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
                    np.allclose(
                        actual, expect, atol=1e-05),
                    "output name: " + out_name + "has diff")

    def __assert_is_close(self, numeric_grad, analytic_grad, name,
                          max_relative_error, msg_prefix):
        abs_a = np.abs(numeric_grad)
        abs_a[abs_a < 1e-3] = 1

        diff_mat = np.abs(numeric_grad - analytic_grad) / abs_a
        max_diff = np.max(diff_mat)

        def err_msg():
            offset = np.argmax(diff_mat > max_relative_error)
            return "%s Variable %s max gradient diff %f over limit %f, the first " \
                  "error element is %d" % (
                   msg_prefix, name, max_diff, max_relative_error, offset)

    def check_grad(self,
                   input_to_check,
                   output_name,
                   no_grad_set=None,
                   in_place=False,
                   max_relative_error=0.005):
        self.scope = core.Scope()
        self.op = create_op(self.scope, self.op_type, self.inputs, self.outputs)
        if no_grad_set is None:
            no_grad_set = set()

        numeric_grad = get_numeric_gradient(
            self.scope,
            self.op,
            self.inputs,
            input_to_check,
            output_name,
            in_place=in_place)
        print numeric_grad

        grad_name = grad_var_name(input_to_check)

        places = [core.CPUPlace()]
        if core.is_compile_gpu() and op.support_gpu():
            places.append(core.GPUPlace(0))

        for place in places:
            analytic_grad = get_gradient(self.scope, self.op, self.inputs,
                                         self.outputs, grad_name, place,
                                         no_grad_set)
            print analytic_grad

            self.__assert_is_close(numeric_grad, analytic_grad, grad_name,
                                   max_relative_error,
                                   "Gradient Check On %s" % str(place))
