"""This module contains methods to compute the gram matrix using various
kernel functions. The obtained gram matrix can be used to train SVMs
with scikit-learn.

The methods are all prepared to work on numpy arrays and take advantage
of vectorial operations to speed up computations.
"""

from collections import defaultdict

import numpy as np

from ..utils import get_pgen, apply_pgen


# Some of the categorical kernels can receive Python functions as parameters.
# For ease of use, some predefined functions can be specified with a string.
# get_function and get_vector_function take this string and return the
# appropiate function. Both are used when handling the kernel parameters.

def get_function(name, params=None):
    params = {} if params is None else params
    if callable(name):
        return name
    elif name == 'ident':
        return lambda k, *args, **kwargs: k(*args, **kwargs)
    elif name == 'f1':
        def f1(k, x, y, *args, **kwargs):
            kxy = k(x, y, *args, **kwargs)
            return np.exp(params['gamma'] * kxy)
        return f1
    elif name == 'f2':
        def f2(k, x, y, *args, **kwargs):
            kxy = k(x, y, *args, **kwargs)
            kxx = k(x, x, *args, **kwargs)
            kyy = k(y, y, *args, **kwargs)
            return np.exp(params['gamma'] * (2.0 * kxy - kxx - kyy))
        return f2
    else:
        raise ValueError("Invalid function {}".format(name))


def get_vector_function(name, params=None):
    params = {} if params is None else params
    if callable(name):
        return name
    elif name == 'ident':
        return lambda x: x
    elif name == 'f1':
        return lambda x: np.exp(params['gamma'] * x)
    elif name == 'f2':
        raise ValueError("Function f2 can't be vectorised")
    else:
        raise ValueError("Invalid function {}".format(name))


# Vectorised kernel functions

def elk(X, Y):
    """Computes a matrix with the values of applying the kernel
    :math:`ELK` between each pair of elements in :math:`X` and :math:`Y`.

    Args:
        X: Numpy matrix.
        Y: Numpy matrix.

    Return:
        Numpy matrix of size :math:`m_X \\times m_Y`.
    """
    xm, xn = X.shape
    ym, yn = Y.shape
    # Compute the kernel matrix:
    G = np.zeros((xm, ym))
    for i in range(xm):
        Xi = np.tile(X[i], (ym, 1))
        Xi = np.sqrt(Xi * Y)
        G[i, :] = np.sum(Xi, axis=1)
    return G


def k0(X, Y, prev='ident', post='ident', **kwargs):
    """Computes a matrix with the values of applying the kernel
    :math:`k_0` between each pair of elements in :math:`X` and :math:`Y`.

    Args:
        X: Numpy matrix.
        Y: Numpy matrix.
        prev (string): Function to transform the data before composing.
            Values: ``'ident'``, ``'f1'`` or a function.
        post (string): Function to transform the data after composing.
            Values: ``'ident'``, ``'f1'`` or a function.
        kwargs (dict): Arguments required by *prev* or *post*.

    Return:
        Numpy matrix of size :math:`m_X \\times m_Y`.

    Since the code is vectorised any function passed in *prev* or *post*
    must work on numpy arrays.
    """
    prevf = get_vector_function(prev, kwargs)
    postf = get_vector_function(post, kwargs)
    xm, xn = X.shape
    ym, yn = Y.shape
    # The gram matrix is computed using vectorised operations because speed:
    G = np.zeros((xm, ym))
    for i in range(xm):
        Xi = np.tile(X[i], (ym, 1))
        Xi = prevf(Xi == Y)
        G[i, :] = np.mean(Xi, axis=1)
    return postf(G)


def k1(X, Y, Xp, Yp, alpha=1.0, prev='ident', post='ident', **kwargs):
    """Computes a matrix with the values of applying the kernel
    :math:`k_1` between each pair of elements in :math:`X` and :math:`Y`.

    Args:
        X: Numpy matrix.
        Y: Numpy matrix.
        alpha (float): Argument for the inverting function *h*.
        Xp: Numpy matrix with the probabilities of each category in *X*.
        Yp: Numpy matrix with the probabilities of each category in *Y*.
        prev (string): Function to transform the data before composing.
            Values: ``'ident'``, ``'f1'`` or a function.
        post (string): Function to transform the data after composing.
            Values: ``'ident'``, ``'f1'``,  ``'f2'`` or a function.
        kwargs (dict): Arguments required by *prev* or *post*.

    Return:
        Numpy matrix of size :math:`m_X \\times m_Y`.

    Since the code is vectorised any function passed in *prev* or *post*
    must work on numpy arrays.
    """
    h = lambda x: (1.0 - x ** alpha) ** (1.0 / alpha)
    prevf = get_vector_function(prev, kwargs)
    postf = get_vector_function(post, kwargs) if post != 'f2' else None
    # The function f2 needs to be treated separately.
    xm, xn = X.shape
    ym, yn = Y.shape
    Yp = h(Yp)
    # The gram matrix is computed using vectorised operations because speed:
    G = np.zeros((xm, ym))
    for i in range(xm):
        Xi = np.tile(X[i], (ym, 1))
        Xi = prevf((Xi == Y) * Yp)
        G[i, :] = np.mean(Xi, axis=1)
    if post != 'f2':
        return postf(G)
    else:
        # We know that: f2 = e ^ (gamma * (2 * k(x, y) - k(x, x) - k(y, y))).
        # The current values of G are those of k(x, y).
        # We need to compute the values of k(x, x) and k(y, y) for each
        # x in X and y in Y:
        gamma = kwargs['gamma']
        Xp = h(Xp)
        GX = np.mean(prevf(Xp), axis=1)
        GX = np.tile(GX, (ym, 1)).T
        GY = np.mean(prevf(Yp), axis=1)
        GY = np.tile(GY, (xm, 1))
        return np.exp(gamma * (2.0 * G - GX - GY))


def k2(X, Y, Xp, Yp, prev='ident', post='ident', **kwargs):
    """Computes a matrix with the values of applying the kernel
    :math:`k_2` between each pair of elements in :math:`X` and :math:`Y`.

    Args:
        X: Numpy matrix.
        Y: Numpy matrix.
        Xp: Numpy matrix with the probabilities of each category in *X*.
        Yp: Numpy matrix with the probabilities of each category in *Y*.
        prev (string): Function to transform the data before composing.
            Values: ``'ident'``, ``'f1'`` or a function.
        post (string): Function to transform the data after composing.
            Values: ``'ident'``, ``'f1'``,  ``'f2'`` or a function.
        kwargs (dict): Arguments required by *prev* or *post*.

    Return:
        Numpy matrix of size :math:`m_X \\times m_Y`.

    Since the code is vectorised any function passed in *prev* or *post*
    must work on numpy arrays.
    """
    prevf = get_vector_function(prev, kwargs)
    postf = get_vector_function(post, kwargs) if post != 'f2' else None
    # The function f2 needs to be treated separately.
    xm, xn = X.shape
    ym, yn = Y.shape
    Yp = 1.0 / Yp
    # The gram matrix is computed using vectorised operations because speed:
    G = np.zeros((xm, ym))
    for i in range(xm):
        Xi = np.tile(X[i], (ym, 1))
        Xi = prevf((Xi == Y) * Yp)
        G[i, :] = np.sqrt(np.sum(Xi, axis=1))
    if post != 'f2':
        return postf(G)
    else:
        # We know that: f2 = e ^ (gamma * (2 * k(x, y) - k(x, x) - k(y, y))).
        # The current values of G are those of k(x, y).
        # We need to compute the values of k(x, x) and k(y, y) for each
        # x in X and y in Y:
        gamma = kwargs['gamma']
        Xp = 1.0 / Xp
        GX = np.sqrt(np.sum(prevf(Xp), axis=1))
        GX = np.tile(GX, (ym, 1)).T
        GY = np.sqrt(np.sum(prevf(Yp), axis=1))
        GY = np.tile(GY, (xm, 1))
        return np.exp(gamma * (2.0 * G - GX - GY))


def m3(X, Y, Xp, Yp, alpha=1.0, prev='ident', post='ident', **kwargs):
    """Computes a matrix with the values of applying the kernel
    :math:`m_1` between each pair of elements in :math:`X` and :math:`Y`.

    Args:
        X: Numpy matrix.
        Y: Numpy matrix.
        Xp: Numpy matrix with the probabilities of each category in *X*.
        Yp: Numpy matrix with the probabilities of each category in *Y*.
        alpha (float): Argument for the inverting function *h*.
        prev (string): Function to transform the data before composing.
            Values: ``'ident'``, ``'f1'`` or a function.
        post (string): Function to transform the data after composing.
            Values: ``'ident'``, ``'f1'``,  ``'f2'`` or a function.
        kwargs (dict): Arguments required by *prev* or *post*.

    Return:
        Numpy matrix of size :math:`m_X \\times m_Y`.

    Since the code is vectorised any function passed in *prev* or *post*
    must work on numpy arrays.
    """
    h = lambda x: (1.0 - x ** alpha) ** (1.0 / alpha)
    prevf = get_vector_function(prev, kwargs)
    postf = get_vector_function(post, kwargs)
    xm, xn = X.shape
    ym, yn = Y.shape
    Xp = h(Xp)
    Yp = h(Yp)
    G = np.zeros((xm, ym))
    for i in range(xm):
        Xi = np.tile(X[i], (ym, 1))
        Xi = prevf((Xi == Y) * Yp)
        Xq = np.tile(Xp[i], (ym, 1))
        Xq = prevf(Xq) + prevf(Yp)
        G[i, :] = 2.0 * np.sum(Xi, axis=1) / np.sum(Xq, axis=1)
    return postf(G)


def m4(X, Y, Xp, Yp, alpha=1.0, prev='ident', post='ident', **kwargs):
    """Computes a matrix with the values of applying the kernel
    :math:`m_4` between each pair of elements in :math:`X` and :math:`Y`.

    Args:
        X: Numpy matrix.
        Y: Numpy matrix.
        Xp: Numpy matrix with the probabilities of each category in *X*.
        Yp: Numpy matrix with the probabilities of each category in *Y*.
        alpha (float): Argument for the inverting function *h*.
        prev (string): Function to transform the data before composing.
            Values: ``'ident'``, ``'f1'`` or a function.
        post (string): Function to transform the data after composing.
            Values: ``'ident'``, ``'f1'``,  ``'f2'`` or a function.
        kwargs (dict): Arguments required by *prev* or *post*.

    Return:
        Numpy matrix of size :math:`m_X \\times m_Y`.

    Since the code is vectorised any function passed in *prev* or *post*
    must work on numpy arrays.
    """
    h = lambda x: (1.0 - x ** alpha) ** (1.0 / alpha)
    prevf = get_vector_function(prev, kwargs)
    postf = get_vector_function(post, kwargs)
    xm, xn = X.shape
    ym, yn = Y.shape
    Xp = h(Xp)
    Yp = h(Yp)
    G = np.zeros((xm, ym))
    for i in range(xm):
        I = np.tile(X[i], (ym, 1))
        Ip = np.tile(Xp[i], (ym, 1))
        EQ = I == Y
        NE = I != Y
        a = 2.0 * np.sum(prevf(Ip * EQ), axis=1)
        b = np.sum(prevf(Ip * NE), axis=1)
        c = np.sum(prevf(Yp * NE), axis=1)
        dx = np.sum(prevf(1.0 - Ip * NE), axis=1)
        dy = np.sum(prevf(1.0 - Ip * NE), axis=1)
        d = dx + dy
        apd = a + d
        G[i, :] = apd / (apd + b + c)
    return postf(G)


def m5(X, Y, Xp, Yp, alpha=1.0, prev='ident', post='ident', **kwargs):
    """Computes a matrix with the values of applying the kernel
    :math:`m_5` between each pair of elements in :math:`X` and :math:`Y`.

    Args:
        X: Numpy matrix.
        Y: Numpy matrix.
        Xp: Numpy matrix with the probabilities of each category in *X*.
        Yp: Numpy matrix with the probabilities of each category in *Y*.
        alpha (float): Argument for the inverting function *h*.
        prev (string): Function to transform the data before composing.
            Values: ``'ident'``, ``'f1'`` or a function.
        post (string): Function to transform the data after composing.
            Values: ``'ident'``, ``'f1'``,  ``'f2'`` or a function.
        kwargs (dict): Arguments required by *prev* or *post*.

    Return:
        Numpy matrix of size :math:`m_X \\times m_Y`.

    Since the code is vectorised any function passed in *prev* or *post*
    must work on numpy arrays.
    """
    h = lambda x: (1.0 - x ** alpha) ** (1.0 / alpha)
    prevf = get_vector_function(prev, kwargs)
    postf = get_vector_function(post, kwargs)
    xm, xn = X.shape
    ym, yn = Y.shape
    Xp = h(Xp)
    Yp = h(Yp)
    G = np.zeros((xm, ym))
    for i in range(xm):
        I = np.tile(X[i], (ym, 1))
        Ip = np.tile(Xp[i], (ym, 1))
        EQ = I == Y
        NE = I != Y
        a = 2.0 * np.sum(prevf(Ip * EQ), axis=1)
        b = np.sum(prevf(Ip * NE), axis=1)
        c = np.sum(prevf(Yp * NE), axis=1)
        G[i, :] = a / (a + 2.0 * (b + c))
    return postf(G)


def m6(X, Y, Xp, Yp, alpha=1.0, prev='ident', post='ident', **kwargs):
    """Computes a matrix with the values of applying the kernel
    :math:`m_4` between each pair of elements in :math:`X` and :math:`Y`.

    Args:
        X: Numpy matrix.
        Y: Numpy matrix.
        Xp: Numpy matrix with the probabilities of each category in *X*.
        Yp: Numpy matrix with the probabilities of each category in *Y*.
        alpha (float): Argument for the inverting function *h*.
        prev (string): Function to transform the data before composing.
            Values: ``'ident'``, ``'f1'`` or a function.
        post (string): Function to transform the data after composing.
            Values: ``'ident'``, ``'f1'``,  ``'f2'`` or a function.
        kwargs (dict): Arguments required by *prev* or *post*.

    Return:
        Numpy matrix of size :math:`m_X \\times m_Y`.

    Since the code is vectorised any function passed in *prev* or *post*
    must work on numpy arrays.
    """
    h = lambda x: (1.0 - x ** alpha) ** (1.0 / alpha)
    prevf = get_vector_function(prev, kwargs)
    postf = get_vector_function(post, kwargs)
    xm, xn = X.shape
    ym, yn = Y.shape
    Xp = h(Xp)
    Yp = h(Yp)
    G = np.zeros((xm, ym))
    for i in range(xm):
        I = np.tile(X[i], (ym, 1))
        Ip = np.tile(Xp[i], (ym, 1))
        EQ = I == Y
        NE = I != Y
        a = 2.0 * np.sum(prevf(Ip * EQ), axis=1)
        b = np.sum(prevf(Ip * NE), axis=1)
        c = np.sum(prevf(Yp * NE), axis=1)
        dx = np.sum(prevf(1.0 - Ip * NE), axis=1)
        dy = np.sum(prevf(1.0 - Ip * NE), axis=1)
        d = dx + dy
        apd = a + d
        G[i, :] = apd / (apd + 2.0 * (b + c))
    return postf(G)


def m7(X, Y, Xp, Yp, alpha=1.0, prev='ident', post='ident', **kwargs):
    """Computes a matrix with the values of applying the kernel
    :math:`m_4` between each pair of elements in :math:`X` and :math:`Y`.

    Args:
        X: Numpy matrix.
        Y: Numpy matrix.
        Xp: Numpy matrix with the probabilities of each category in *X*.
        Yp: Numpy matrix with the probabilities of each category in *Y*.
        alpha (float): Argument for the inverting function *h*.
        prev (string): Function to transform the data before composing.
            Values: ``'ident'``, ``'f1'`` or a function.
        post (string): Function to transform the data after composing.
            Values: ``'ident'``, ``'f1'``,  ``'f2'`` or a function.
        kwargs (dict): Arguments required by *prev* or *post*.

    Return:
        Numpy matrix of size :math:`m_X \\times m_Y`.

    Since the code is vectorised any function passed in *prev* or *post*
    must work on numpy arrays.
    """
    h = lambda x: (1.0 - x ** alpha) ** (1.0 / alpha)
    prevf = get_vector_function(prev, kwargs)
    postf = get_vector_function(post, kwargs)
    xm, xn = X.shape
    ym, yn = Y.shape
    Xp = h(Xp)
    Yp = h(Yp)
    G = np.zeros((xm, ym))
    for i in range(xm):
        I = np.tile(X[i], (ym, 1))
        Ip = np.tile(Xp[i], (ym, 1))
        EQ = I == Y
        NE = I != Y
        a = 2.0 * np.sum(prevf(Ip * EQ), axis=1)
        b = np.sum(prevf(Ip * NE), axis=1)
        c = np.sum(prevf(Yp * NE), axis=1)
        G[i, :] = a / (a + (b + c) / 2.0)
    return postf(G)


def m8(X, Y, Xp, Yp, alpha=1.0, prev='ident', post='ident', **kwargs):
    """Computes a matrix with the values of applying the kernel
    :math:`m_4` between each pair of elements in :math:`X` and :math:`Y`.

    Args:
        X: Numpy matrix.
        Y: Numpy matrix.
        Xp: Numpy matrix with the probabilities of each category in *X*.
        Yp: Numpy matrix with the probabilities of each category in *Y*.
        alpha (float): Argument for the inverting function *h*.
        prev (string): Function to transform the data before composing.
            Values: ``'ident'``, ``'f1'`` or a function.
        post (string): Function to transform the data after composing.
            Values: ``'ident'``, ``'f1'``,  ``'f2'`` or a function.
        kwargs (dict): Arguments required by *prev* or *post*.

    Return:
        Numpy matrix of size :math:`m_X \\times m_Y`.

    Since the code is vectorised any function passed in *prev* or *post*
    must work on numpy arrays.
    """
    h = lambda x: (1.0 - x ** alpha) ** (1.0 / alpha)
    prevf = get_vector_function(prev, kwargs)
    postf = get_vector_function(post, kwargs)
    xm, xn = X.shape
    ym, yn = Y.shape
    Xp = h(Xp)
    Yp = h(Yp)
    G = np.zeros((xm, ym))
    for i in range(xm):
        I = np.tile(X[i], (ym, 1))
        Ip = np.tile(Xp[i], (ym, 1))
        EQ = I == Y
        NE = I != Y
        a = 2.0 * np.sum(prevf(Ip * EQ), axis=1)
        b = np.sum(prevf(Ip * NE), axis=1)
        c = np.sum(prevf(Yp * NE), axis=1)
        dx = np.sum(prevf(1.0 - Ip * NE), axis=1)
        dy = np.sum(prevf(1.0 - Ip * NE), axis=1)
        d = dx + dy
        apd = a + d
        G[i, :] = apd / (apd + (b + c) / 2.0)
    return postf(G)


def m9(X, Y, Xp, Yp, alpha=1.0, prev='ident', post='ident', **kwargs):
    """Computes a matrix with the values of applying the kernel
    :math:`m_4` between each pair of elements in :math:`X` and :math:`Y`.

    Args:
        X: Numpy matrix.
        Y: Numpy matrix.
        Xp: Numpy matrix with the probabilities of each category in *X*.
        Yp: Numpy matrix with the probabilities of each category in *Y*.
        alpha (float): Argument for the inverting function *h*.
        prev (string): Function to transform the data before composing.
            Values: ``'ident'``, ``'f1'`` or a function.
        post (string): Function to transform the data after composing.
            Values: ``'ident'``, ``'f1'``,  ``'f2'`` or a function.
        kwargs (dict): Arguments required by *prev* or *post*.

    Return:
        Numpy matrix of size :math:`m_X \\times m_Y`.

    Since the code is vectorised any function passed in *prev* or *post*
    must work on numpy arrays.
    """
    h = lambda x: (1.0 - x ** alpha) ** (1.0 / alpha)
    prevf = get_vector_function(prev, kwargs)
    postf = get_vector_function(post, kwargs)
    xm, xn = X.shape
    ym, yn = Y.shape
    Xp = h(Xp)
    Yp = h(Yp)
    G = np.zeros((xm, ym))
    for i in range(xm):
        I = np.tile(X[i], (ym, 1))
        Ip = np.tile(Xp[i], (ym, 1))
        EQ = I == Y
        NE = I != Y
        a = 2.0 * np.sum(prevf(Ip * EQ), axis=1)
        b = np.sum(prevf(Ip * NE), axis=1)
        c = np.sum(prevf(Yp * NE), axis=1)
        dx = np.sum(prevf(1.0 - Ip * NE), axis=1)
        dy = np.sum(prevf(1.0 - Ip * NE), axis=1)
        d = dx + dy
        bpc = b + c
        apd = a + d
        G[i, :] = (apd - bpc) / (apd + bpc)
    return postf(G)


def mA(X, Y, Xp, Yp, alpha=1.0, prev='ident', post='ident', **kwargs):
    """Computes a matrix with the values of applying the kernel
    :math:`m_5` between each pair of elements in :math:`X` and :math:`Y`.

    Args:
        X: Numpy matrix.
        Y: Numpy matrix.
        Xp: Numpy matrix with the probabilities of each category in *X*.
        Yp: Numpy matrix with the probabilities of each category in *Y*.
        alpha (float): Argument for the inverting function *h*.
        prev (string): Function to transform the data before composing.
            Values: ``'ident'``, ``'f1'`` or a function.
        post (string): Function to transform the data after composing.
            Values: ``'ident'``, ``'f1'``,  ``'f2'`` or a function.
        kwargs (dict): Arguments required by *prev* or *post*.

    Return:
        Numpy matrix of size :math:`m_X \\times m_Y`.

    Since the code is vectorised any function passed in *prev* or *post*
    must work on numpy arrays.
    """
    h = lambda x: (1.0 - x ** alpha) ** (1.0 / alpha)
    prevf = get_vector_function(prev, kwargs)
    postf = get_vector_function(post, kwargs)
    xm, xn = X.shape
    ym, yn = Y.shape
    Xp = h(Xp)
    Yp = h(Yp)
    G = np.zeros((xm, ym))
    for i in range(xm):
        I = np.tile(X[i], (ym, 1))
        Ip = np.tile(Xp[i], (ym, 1))
        EQ = I == Y
        NE = I != Y
        a = 2.0 * np.sum(prevf(Ip * EQ), axis=1)
        b = np.sum(prevf(Ip * NE), axis=1)
        c = np.sum(prevf(Yp * NE), axis=1)
        G[i, :] = (a / (a + b) + a / (a + c)) / 2.0
    return postf(G)


def mB(X, Y, Xp, Yp, alpha=1.0, prev='ident', post='ident', **kwargs):
    """Computes a matrix with the values of applying the kernel
    :math:`m_4` between each pair of elements in :math:`X` and :math:`Y`.

    Args:
        X: Numpy matrix.
        Y: Numpy matrix.
        Xp: Numpy matrix with the probabilities of each category in *X*.
        Yp: Numpy matrix with the probabilities of each category in *Y*.
        alpha (float): Argument for the inverting function *h*.
        prev (string): Function to transform the data before composing.
            Values: ``'ident'``, ``'f1'`` or a function.
        post (string): Function to transform the data after composing.
            Values: ``'ident'``, ``'f1'``,  ``'f2'`` or a function.
        kwargs (dict): Arguments required by *prev* or *post*.

    Return:
        Numpy matrix of size :math:`m_X \\times m_Y`.

    Since the code is vectorised any function passed in *prev* or *post*
    must work on numpy arrays.
    """
    h = lambda x: (1.0 - x ** alpha) ** (1.0 / alpha)
    prevf = get_vector_function(prev, kwargs)
    postf = get_vector_function(post, kwargs)
    xm, xn = X.shape
    ym, yn = Y.shape
    Xp = h(Xp)
    Yp = h(Yp)
    G = np.zeros((xm, ym))
    for i in range(xm):
        I = np.tile(X[i], (ym, 1))
        Ip = np.tile(Xp[i], (ym, 1))
        EQ = I == Y
        NE = I != Y
        a = 2.0 * np.sum(prevf(Ip * EQ), axis=1)
        b = np.sum(prevf(Ip * NE), axis=1)
        c = np.sum(prevf(Yp * NE), axis=1)
        dx = np.sum(prevf(1.0 - Ip * NE), axis=1)
        dy = np.sum(prevf(1.0 - Ip * NE), axis=1)
        d = dx + dy
        G[i, :] = (a / (a + b) + a / (a + c) + d / (d + b) + d / (d + c)) / 4.0
    return postf(G)


def mC(X, Y, Xp, Yp, alpha=1.0, prev='ident', post='ident', **kwargs):
    """Computes a matrix with the values of applying the kernel
    :math:`m_5` between each pair of elements in :math:`X` and :math:`Y`.

    Args:
        X: Numpy matrix.
        Y: Numpy matrix.
        Xp: Numpy matrix with the probabilities of each category in *X*.
        Yp: Numpy matrix with the probabilities of each category in *Y*.
        alpha (float): Argument for the inverting function *h*.
        prev (string): Function to transform the data before composing.
            Values: ``'ident'``, ``'f1'`` or a function.
        post (string): Function to transform the data after composing.
            Values: ``'ident'``, ``'f1'``,  ``'f2'`` or a function.
        kwargs (dict): Arguments required by *prev* or *post*.

    Return:
        Numpy matrix of size :math:`m_X \\times m_Y`.

    Since the code is vectorised any function passed in *prev* or *post*
    must work on numpy arrays.
    """
    h = lambda x: (1.0 - x ** alpha) ** (1.0 / alpha)
    prevf = get_vector_function(prev, kwargs)
    postf = get_vector_function(post, kwargs)
    xm, xn = X.shape
    ym, yn = Y.shape
    Xp = h(Xp)
    Yp = h(Yp)
    G = np.zeros((xm, ym))
    for i in range(xm):
        I = np.tile(X[i], (ym, 1))
        Ip = np.tile(Xp[i], (ym, 1))
        EQ = I == Y
        NE = I != Y
        a = 2.0 * np.sum(prevf(Ip * EQ), axis=1)
        b = np.sum(prevf(Ip * NE), axis=1)
        c = np.sum(prevf(Yp * NE), axis=1)
        G[i, :] = a / np.sqrt((a + b) * (a + c))
    return postf(G)


def mD(X, Y, Xp, Yp, alpha=1.0, prev='ident', post='ident', **kwargs):
    """Computes a matrix with the values of applying the kernel
    :math:`m_4` between each pair of elements in :math:`X` and :math:`Y`.

    Args:
        X: Numpy matrix.
        Y: Numpy matrix.
        Xp: Numpy matrix with the probabilities of each category in *X*.
        Yp: Numpy matrix with the probabilities of each category in *Y*.
        alpha (float): Argument for the inverting function *h*.
        prev (string): Function to transform the data before composing.
            Values: ``'ident'``, ``'f1'`` or a function.
        post (string): Function to transform the data after composing.
            Values: ``'ident'``, ``'f1'``,  ``'f2'`` or a function.
        kwargs (dict): Arguments required by *prev* or *post*.

    Return:
        Numpy matrix of size :math:`m_X \\times m_Y`.

    Since the code is vectorised any function passed in *prev* or *post*
    must work on numpy arrays.
    """
    h = lambda x: (1.0 - x ** alpha) ** (1.0 / alpha)
    prevf = get_vector_function(prev, kwargs)
    postf = get_vector_function(post, kwargs)
    xm, xn = X.shape
    ym, yn = Y.shape
    Xp = h(Xp)
    Yp = h(Yp)
    G = np.zeros((xm, ym))
    for i in range(xm):
        I = np.tile(X[i], (ym, 1))
        Ip = np.tile(Xp[i], (ym, 1))
        EQ = I == Y
        NE = I != Y
        a = 2.0 * np.sum(prevf(Ip * EQ), axis=1)
        b = np.sum(prevf(Ip * NE), axis=1)
        c = np.sum(prevf(Yp * NE), axis=1)
        dx = np.sum(prevf(1.0 - Ip * NE), axis=1)
        dy = np.sum(prevf(1.0 - Ip * NE), axis=1)
        d = dx + dy
        # nz = np.amax(NE, axis=1)
        # eo = np.amin(EQ, axis=1)
        num = (a * d)  # * nz + eo
        den = np.sqrt((a + b) * (a + c) * (d + b) * (d + c))  # * nz + eo
        G[i, :] = num / den
    return postf(G)


def mE(X, Y, Xp, Yp, alpha=1.0, prev='ident', post='ident', **kwargs):
    """Computes a matrix with the values of applying the kernel
    :math:`m_4` between each pair of elements in :math:`X` and :math:`Y`.

    Args:
        X: Numpy matrix.
        Y: Numpy matrix.
        Xp: Numpy matrix with the probabilities of each category in *X*.
        Yp: Numpy matrix with the probabilities of each category in *Y*.
        alpha (float): Argument for the inverting function *h*.
        prev (string): Function to transform the data before composing.
            Values: ``'ident'``, ``'f1'`` or a function.
        post (string): Function to transform the data after composing.
            Values: ``'ident'``, ``'f1'``,  ``'f2'`` or a function.
        kwargs (dict): Arguments required by *prev* or *post*.

    Return:
        Numpy matrix of size :math:`m_X \\times m_Y`.

    Since the code is vectorised any function passed in *prev* or *post*
    must work on numpy arrays.
    """
    h = lambda x: (1.0 - x ** alpha) ** (1.0 / alpha)
    prevf = get_vector_function(prev, kwargs)
    postf = get_vector_function(post, kwargs)
    xm, xn = X.shape
    ym, yn = Y.shape
    Xp = h(Xp)
    Yp = h(Yp)
    G = np.zeros((xm, ym))
    for i in range(xm):
        I = np.tile(X[i], (ym, 1))
        Ip = np.tile(Xp[i], (ym, 1))
        EQ = I == Y
        NE = I != Y
        a = 2.0 * np.sum(prevf(Ip * EQ), axis=1)
        b = np.sum(prevf(Ip * NE), axis=1)
        c = np.sum(prevf(Yp * NE), axis=1)
        dx = np.sum(prevf(1.0 - Ip * NE), axis=1)
        dy = np.sum(prevf(1.0 - Ip * NE), axis=1)
        d = dx + dy
        # nz = np.amax(NE, axis=1)
        # eo = np.amin(EQ, axis=1)
        num = (a * d - b * c)  # * nz + eo
        den = np.sqrt((a + b) * (a + c) * (d + b) * (d + c))  # * nz + eo
        G[i, :] = num / den
    return postf(G)


def chi1(X, Y, **kwargs):
    Xm, Xn = X.shape
    Ym, Yn = Y.shape
    G = np.zeros((Xm, Ym))
    for i, Xi in enumerate(X):
        for j, Yj in enumerate(Y):
            counter = defaultdict(int)
            for k in range(Xn):
                counter[(Xi[k], Yj[k])] += 1
            for k in range(Xn):
                ABCD = np.zeros((2, 2))
                for pair, count in counter.items():
                    r = 0 if Xi[k] == pair[0] else 1
                    s = 0 if Yj[k] == pair[1] else 1
                    ABCD[r, s] += count
                a = ABCD[0, 0]
                b = ABCD[0, 1]
                c = ABCD[1, 0]
                d = ABCD[1, 1]
                num = Xn * (a*d - c*b) ** 2
                den = (a+c) * (b+d) * (a+b) * (c+d)
                G[i, j] += num / den
    return G


def chi2(X, Y, **kwargs):
    Xm, Xn = X.shape
    Ym, Yn = Y.shape
    G = np.zeros((Xm, Ym))
    counter = defaultdict(int)
    for i, Yi in enumerate(Y):
        for j, Yj in enumerate(Y):
            for k in range(Yn):
                counter[(Yi[k], Yj[k])] += 1
    for i, Xi in enumerate(X):
        for j, Yj in enumerate(Y):
            for k in range(Xn):
                ABCD = np.zeros((2, 2))
                for pair, count in counter.items():
                    r = 0 if Xi[k] == pair[0] else 1
                    s = 0 if Yj[k] == pair[1] else 1
                    ABCD[r, s] += count
                a = ABCD[0, 0]
                b = ABCD[0, 1]
                c = ABCD[1, 0]
                d = ABCD[1, 1]
                num = Xn * (a*d - c*b) ** 2
                den = (a+c) * (b+d) * (a+b) * (c+d)
                G[i, j] += num / den
    return G
