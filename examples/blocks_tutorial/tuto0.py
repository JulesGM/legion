__author__ = 'Jules Gagnon-Marchand'
import os, sys, re
from traceback import format_exc

from theano import tensor
from blocks.algorithms import GradientDescent, Scale
import argparse
import numpy as np
from fuel.datasets import MNIST

from fuel.datasets import MNIST
from fuel.streams import DataStream
from fuel.schemes import SequentialScheme
from fuel.transformers import Flatten
from blocks.bricks import Linear, Rectifier, Softmax
from blocks.bricks.cost import CategoricalCrossEntropy
from blocks.extensions.monitoring import DataStreamMonitoring
from blocks.main_loop import MainLoop
from blocks.extensions import FinishAfter, Printing
from blocks.bricks import WEIGHT, BIAS
from blocks.graph import ComputationGraph
from blocks.filter import VariableFilter
from blocks.initialization import IsotropicGaussian, Constant

from legion.blocks_extensions import SharedParamsAutoSync, SharedParamsRateLimited


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("every_n_batches", type=int, default=[1], nargs=1)
    args = parser.parse_args()
    print("We were asked to sync with legion at every_n_batches = %s" % str(args.every_n_batches[0]))


    # The rest is a copy paste from the blocks tutorial, except for the inclusion of the sync extension
    # at the creation of the MainLoop blocks object.
    x = tensor.matrix('features')

    input_to_hidden = Linear(name='input_to_hidden', input_dim=784, output_dim=100)
    h = Rectifier().apply(input_to_hidden.apply(x))
    hidden_to_output = Linear(name='hidden_to_output', input_dim=100, output_dim=10)
    y_hat = Softmax().apply(hidden_to_output.apply(h))

    y = tensor.lmatrix('targets')

    cost = CategoricalCrossEntropy().apply(y.flatten(), y_hat)

    cg = ComputationGraph(cost)

    W1, W2 = VariableFilter(roles=[WEIGHT])(cg.variables)
    
    cost = cost + 0.005 * (W1 ** 2).sum() + 0.005 * (W2 ** 2).sum()
    cost.name = 'cost_with_regularization'

    input_to_hidden.weights_init = hidden_to_output.weights_init = IsotropicGaussian(0.01)
    input_to_hidden.biases_init = hidden_to_output.biases_init = Constant(0)
    input_to_hidden.initialize()
    hidden_to_output.initialize()

    mnist = MNIST(("train",))
    data_stream = Flatten(
        DataStream.default_stream(
            mnist,
            iteration_scheme=SequentialScheme(mnist.num_examples, batch_size=256)))

    algorithm = GradientDescent(
        cost=cost,
        params=cg.parameters,
        step_rule=Scale(learning_rate=0.1)
    )

    mnist_test = MNIST(("test",))
    
    data_stream_test = Flatten(DataStream.default_stream(
        mnist_test,
        iteration_scheme=SequentialScheme(mnist_test.num_examples,
                                          batch_size=1024)))

    monitor = DataStreamMonitoring(variables=[cost],
                                   data_stream=data_stream_test,
                                   prefix="test")

    # Except for this line
    b1, b2 = VariableFilter(roles=[BIAS])(cg.variables)
    
    main_loop = MainLoop(data_stream=data_stream,
                         algorithm=algorithm,
                         extensions=[monitor,
                                     FinishAfter(after_n_epochs=500),
                                     Printing(),
                                     # And the inclusion of the legion sync module, SharedParamsRateLimited:
                                     SharedParamsRateLimited(
                                         params={"W1": W1,
                                                 "W2": W2,
                                                 "b1": b1,
                                                 "b2": b2
                                                 },
                                         alpha=.5,
                                         beta=.5,
                                         every_n_batches=args.every_n_batches[0],
                                         maximum_rate=0.1)])
    main_loop.run()

if __name__ == "__main__":
    main()
