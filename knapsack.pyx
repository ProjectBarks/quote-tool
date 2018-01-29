cimport numpy as np
from cpython cimport array
import numpy as np


cdef _knapsack(float[:] values, int[:] weights, int max_weight):
    # Create rows and columns
    cdef int rows = len(weights) + 1
    cdef int cols = max_weight + 1
    # Generate matrix
    cdef np.ndarray[double, ndim=2] dp_array = np.zeros((rows, cols))

    # Define variables outside of loop
    cdef double value # temp value
    cdef int weight # temp weight
    cdef int i # x index
    cdef int j # y index
    for i in range(1, rows):
        # weights
        for j in range(1, cols):
            weight = weights[i - 1]
            if j - weight >= 0:
                value = values[i - 1]
                dp_array[i][j] = max(dp_array[i - 1][j], value + dp_array[i - 1][j - weight])
            else:
                dp_array[i][j] = dp_array[i - 1][j]

    # final result
    return dp_array[rows - 1][cols - 1]

def knapsack(values, weights, max_weight):
    """
    Using two separated lists the values will be translated into cython and than ran through a c knapsack algorithm.
    This acts primarily as a translation layer

    :param values: list of doubles
    :param weights: list of ints
    :param max_weight: an int
    :return: returns optimal value as a double
    """
    cdef float[:] v = array.array('f', values)
    cdef int[:] w = array.array('i', weights)
    return _knapsack(v, w, max_weight)

__all__= ['knapsack']