# Copyright (c) 2010 Matej Laitl <matej@laitl.cz>
# Distributed under the terms of the GNU General Public License v2 or any
# later version of the license, at your option.

"""
This module contains models of common probability density functions, abbreviated
as pdfs.

All classes from this module are currently imported to top-level pybayes module,
so instead of ``from pybayes.pdfs import Pdf`` you can type ``from pybayes import
Pdf``.
"""

from copy import deepcopy
from math import log, sqrt  # TODO: use numpy versions?

from numpywrap import *


class RVComp(object):
    """Atomic component of a random variable.

    :var int dimension: dimension; do not change unless you know what you are doing
    :var str name: name; can be changed as long as it remains a string (warning:
       parent RVs are not updated)
    """

    def __init__(self, dimension, name = None):
        """Initialise new component of a random variable :class:`RV`.

        :param dimension: number of vector components this component occupies
        :type dimension: positive integer
        :param name: name of the component; default: None for anonymous component
        :type name: string or None
        :raises TypeError: non-integer dimension or non-string name
        :raises ValueError: non-positive dimension
        """

        if name is not None and not isinstance(name, str):
            raise TypeError("name must be either None or a string")
        self.name = name
        if not isinstance(dimension, int):
            raise TypeError("dimension must be integer (int)")
        if dimension < 1:
            raise ValueError("dimension must be non-zero positive")
        self.dimension = dimension

    #def __eq__(self, other):
        #"""We want RVComp have to be hashable
        #(http://docs.python.org/glossary.html#term-hashable), but default __eq__()
        #and __hash__() implementations suffice, as they are instance-based.
        #"""


class RV(object):
    """Representation of a random variable made of one or more components. Each component is
    represented by :class:`RVComp` class.

    :var int dimension: cummulative dimension; do not change
    :var str name: pretty name, can be changed but needs to be a string
    :var list components: list of RVComps; do not change

    *Please take into account that all RVComp comparisons inside RV are
    instance-based and component names are purely informational. To demonstrate:*

    >>> rv = RV(RVComp(1, "a"))
    >>> ...
    >>> rv.contains(RVComp(1, "a"))
    False

    Right way to do this would be:

    >>> a = RVComp(1, "arbitrary pretty name for a")
    >>> rv = RV(a)
    >>> ...
    >>> rv.contains(a)
    True
    """

    def __init__(self, *components):
        """Initialise random variable meta-representation.

        :param \*components: components that should form the random variable. You may
            also pass another RVs which is a shotrcut for adding all their components.
        :type \*components: :class:`RV`, :class:`RVComp` or a sequence of :class:`RVComp` items
        :raises TypeError: invalid object passed (neither a :class:`RV` or a :class:`RVComp`)

        Usual way of creating a RV could be:

        >>> x = RV(RVComp(1, 'x_1'), RVComp(1, 'x_2'))
        >>> x.name
        '[x_1, x_2]'
        >>> xy = RV(x, RVComp(2, 'y'))
        >>> xy.name
        '[x_1, x_2, y]'
        """
        self.dimension = 0
        self.components = []
        if len(components) is 0:
            self.name = '[]'
            return

        self.name = '['
        for component in components:
            if isinstance(component, RVComp):
                self._add_component(component)
            elif isinstance(component, RV):
                for subcomp in component.components:
                    self._add_component(subcomp)
            else:
                try:
                    for subcomp in component:
                        self._add_component(subcomp)
                except TypeError:
                    raise TypeError('component ' + str(component) + ' is neither an instance '
                                + 'of RVComp or RV and is not iterable of RVComps')
        self.name = self.name[:-2] + ']'

    def __copy__(self):
        ret = type(self).__new__(type(self))
        ret.name = self.name
        ret.dimension = self.dimension
        ret.components = self.components
        return ret

    def __deepcopy__(self, memo):
        ret = type(self).__new__(type(self))
        ret.name = self.name  # no need to deepcopy - string is immutable
        ret.dimension = self.dimension  # ditto
        # Following shallow copy is special behaviour of RV:
        ret.components = self.components[:]
        return ret

    def _add_component(self, component):
        """Add new component to this random variable.

        Internal function, do not use outside of RV."""
        if not isinstance(component, RVComp):
            raise TypeError("component is not of type RVComp")
        self.components.append(component)
        self.dimension += component.dimension
        self.name = '{0}{1}, '.format(self.name, component.name)
        return True

    def contains(self, component):
        """Return True if this random variable contains the exact same instance of
        the **component**.

        :param component: component whose presence is tested
        :type component: :class:`RVComp`
        :rtype: bool
        """
        return component in self.components

    def contains_all(self, test_components):
        """Return True if this RV contains all RVComps from sequence
        **test_components**.

        :param test_components: list of components whose presence is checked
        :type test_components: sequence of :class:`RVComp` items
        """
        for test_comp in test_components:
            if not self.contains(test_comp):
                return False
        return True;

    def contains_any(self, test_components):
        """Return True if this RV contains any of **test_components**.

        :param test_components: sequence of components whose presence is tested
        :type test_components: sequence of :class:`RVComp` items
        """
        for test_comp in test_components:
            if self.contains(test_comp):
                return True
        return False

    def contained_in(self, test_components):
        """Return True if sequence **test_components** contains all components
        from this RV (and perhaps more).

        :param test_components: set of components whose presence is checked
        :type test_components: sequence of :class:`RVComp` items
        """
        for component in self.components:
            if component not in test_components:
                return False
        return True

    def indexed_in(self, super_rv):
        """Return index array such that this rv is indexed in **super_rv**, which
        must be a superset of this rv. Resulting array can be used with :func:`numpy.take`
        and :func:`numpy.put`.

        :param super_rv: returned indices apply to this rv
        :type super_rv: :class:`RV`
        :rtype: 1D :class:`numpy.ndarray` of ints with dimension = self.dimension
        """
        ret = empty(self.dimension, dtype=int)
        ret_ind = 0  # current index in returned index array
        # process each component from target rv
        for comp in self.components:
            # find associated component in source_rv components:
            src_ind = 0  # index in source vector
            for source_comp in super_rv.components:
                if source_comp is comp:
                    ret[ret_ind:] = arange(src_ind, src_ind + comp.dimension)
                    ret_ind += comp.dimension
                    break;
                src_ind += source_comp.dimension
            else:
                raise AttributeError("Cannont find component "+str(comp)+" in source_rv.components.")
        return ret

    def __str__(self):
        return "<pybayes.pdfs.RV '{0}' dim={1} {2}>".format(self.name, self.dimension, self.components)


class CPdf(object):
    r"""Base class for all Conditional (in general) Probability Density Functions.

    When you evaluate a CPdf the result generally also depends on a condition
    (vector) named `cond` in PyBayes. For a CPdf that is a :class:`Pdf` this is
    not the case, the result is unconditional.

    Every CPdf takes (apart from others) 2 optional arguments to constructor:
    **rv** (:class:`RV`) and **cond_rv** (:class:`RV`). When specified, they
    denote that the CPdf is associated with a particular random variable (respectively
    its condition is associated with a particular random variable); when unspecified,
    *anonymous* random variable is assumed (exceptions exist, see :class:`ProdPdf`).
    It is an error to pass RV whose dimension is not same as CPdf's dimension
    (or cond dimension respectively).

    :var RV rv: associated random variable (always set in constructor, contains
       at least one RVComp)
    :var RV cond_rv: associated condition random variable (set in constructor to
       potentially empty RV)

    *While you can assign different rv and cond_rv to a CPdf, you should be
    cautious because sanity checks are only performed in constructor.*

    While entire idea of random variable associations may not be needed in simple
    cases, it allows you to express more complicated situations. Assume the state
    variable is composed of 2 components :math:`x_t = [a_t, b_t]` and following
    probability density function has to be modelled:

    .. math::

       p(x_t|x_{t-1}) &:= p_1(a_t|a_{t-1}, b_t) p_2(b_t|b_{t-1}) \\
       p_1(a_t|a_{t-1}, b_t) &:= \mathcal{N}(a_{t-1}, b_t) \\
       p_2(b_t|b_{t-1}) &:= \mathcal{N}(b_{t-1}, 0.0001)

    This is done in PyBayes with associated RVs:

    >>> a_t, b_t = RVComp(1, 'a_t'), RVComp(1, 'b_t')  # create RV components
    >>> a_tp, b_tp = RVComp(1, 'a_{t-1}'), RVComp(1, 'b_{t-1}')  # t-1 case

    >>> p1 = LinGaussCPdf(1., 0., 1., 0., RV(a_t), RV(a_tp, b_t))
    >>> # params for p2:
    >>> cov, A, b = np.array([[0.0001]]), np.array([[1.]]), np.array([0.])
    >>> p2 = MLinGaussCPdf(cov, A, b, RV(b_t), RV(b_tp))

    >>> p = ProdCPdf((p1, p2), RV(a_t, b_t), RV(a_tp, b_tp))

    >>> p.sample(np.array([1., 2.]))
    >>> p.eval_log()
    """

    def shape(self):
        """Return shape of the random variable. :meth:`mean` and :meth:`variance` methods must
        return arrays of this shape.

        :rtype: int"""
        raise NotImplementedError("Derived classes must implement this function")

    def cond_shape(self):
        """Return shape of the condition.

        :rtype: int"""
        raise NotImplementedError("Derived classes must implement this function")

    def mean(self, cond = None):
        """Return (conditional) mean value of the pdf.

        :rtype: :class:`numpy.ndarray`"""
        raise NotImplementedError("Derived classes must implement this function")

    def variance(self, cond = None):
        """Return (conditional) variance (diagonal elements of covariance).

        :rtype: :class:`numpy.ndarray`"""
        raise NotImplementedError("Derived classes must implement this function")

    def eval_log(self, x, cond = None):
        """Return logarithm of (conditional) likelihood function in point x.

        :param x: point which to evaluate the function in
        :type x: :class:`numpy.ndarray`
        :rtype: double"""
        raise NotImplementedError("Derived classes must implement this function")

    def sample(self, cond = None):
        """Return one random (conditional) sample from this distribution

        :rtype: :class:`numpy.ndarray`"""
        raise NotImplementedError("Derived classes must implement this function")

    def samples(self, n, cond = None):
        """Return n samples in an array. A convenience function that just calls
        :meth:`shape` multiple times.

        :param int n: number of samples to return
        :rtype: 2D :class:`numpy.ndarray` of shape (*n*, m) where m is pdf
           dimension"""
        ret = empty((n, self.shape()))
        for i in range(n):
            ret[i] = self.sample(cond)
        return ret

    def _check_cond(self, cond):
        """Return True if cond has correct type and shape, raise Error otherwise.

        :raises TypeError: cond is not of correct type
        :raises ValueError: cond doesn't have appropriate shape
        :rtype: bool"""
        if cond is None:  # cython-specific
            raise TypeError("cond must be numpy.ndarray")
        if cond.ndim != 1:
            raise ValueError("cond must be 1D numpy array (a vector)")
        if cond.shape[0] != self.cond_shape():
            raise ValueError("cond must be of shape ({0},) array of shape ({1},) given".format(self.cond_shape(), cond.shape[0]))
        return True

    def _check_x(self, x):
        """Return True if x has correct type and shape (determined by shape()),
        raise Error otherwise.

        :raises TypeError: cond is not of correct type
        :raises ValueError: cond doesn't have appropriate shape
        :rtype: bool"""
        if x is None:  # cython-specific
            raise TypeError("x must be numpy.ndarray")
        if x.ndim != 1:
            raise ValueError("x must be 1D numpy array (a vector)")
        if x.shape[0] != self.shape():
            raise ValueError("x must be of shape ({0},) array of shape ({1},) given".format(self.shape(), x.shape[0]))
        return True

    def _set_rvs(self, rv, cond_rv):
        """Internal heper to check and set rv and cond_rv.

        :raises TypeError: rv or cond_rv doesnt have right type
        :raises ValueError: dimensions do not match"""
        if rv is None:
            self.rv = RV(RVComp(self.shape()))  # create RV with one anonymous component
        else:
            if not isinstance(rv, RV):
                raise TypeError("rv (if specified) must be (a subclass of) RV")
            if rv.dimension != self.shape():
                raise ValueError("rv has wrong dimension " + str(rv.dimension) + ", " + str(self.shape()) + " expected")
            self.rv = rv

        if cond_rv is None:
            if self.cond_shape() is 0:
                self.cond_rv = RV()  # create empty RV to denote empty condition
            else:
                self.cond_rv = RV(RVComp(self.cond_shape()))  # create RV with one anonymous component
        else:
            if not isinstance(cond_rv, RV):
                raise TypeError("cond_rv (is specified) must be (a subclass of) RV")
            if cond_rv.dimension is not self.cond_shape():
                raise ValueError("cond_rv has wrong dimension " + str(cond_rv.dimension) + ", " + str(self.cond_shape()) + " expected")
            self.cond_rv = cond_rv
        return True


class Pdf(CPdf):
    """Base class for all unconditional (static) multivariate Probability Density
    Functions. Subclass of :class:`CPdf`.

    As in CPdf, constructor of every Pdf takes optional **rv** (:class:`RV`)
    keyword argument (and no *cond_rv* argument as it would make no sense). For
    discussion about associated random variables see :class:`CPdf`.
    """

    def cond_shape(self):
        """Return zero as Pdfs have no condition."""
        return 0


class UniPdf(Pdf):
    r"""Simple uniform multivariate probability density function. Extends
    :class:`Pdf`.

    .. math:: f(x) = \Theta(x - a) \Theta(b - x) \prod_{i=1}^n \frac{1}{b_i-a_i}

    :var a: left border
    :type a: :class:`numpy.ndarray`
    :var b: right border
    :type b: :class:`numpy.ndarray`

    You may modify these attributes as long as you don't change their shape and
    assumption **a** < **b** still holds.
    """

    def __init__(self, a, b, rv = None):
        """Initialise uniform distribution.

        :param a: left border
        :type a: :class:`numpy.ndarray`
        :param b: right border
        :type b: :class:`numpy.ndarray`

        **b** must be greater (in each dimension) than **a**
        """
        self.a = asarray(a)
        self.b = asarray(b)
        if a.ndim != 1 or b.ndim != 1:
            raise ValueError("both a and b must be 1D numpy arrays (vectors)")
        if a.shape[0] != b.shape[0]:
            raise ValueError("a must have same shape as b")
        if np_any(self.b <= self.a):
            raise ValueError("b must be greater than a in each dimension")
        self._set_rvs(rv, None)

    def shape(self):
        return self.a.shape[0]

    def mean(self, cond = None):
        return (self.a+self.b)/2.  # element-wise division

    def variance(self, cond = None):
        return ((self.b-self.a)**2)/12.  # element-wise power and division

    def eval_log(self, x, cond = None):
        self._check_x(x)
        if np_any(x <= self.a) or np_any(x >= self.b):
            return float('-inf')
        return -log(prod(self.b-self.a))

    def sample(self, cond = None):
        return random.uniform(-0.5, 0.5, self.shape()) * (self.b-self.a) + self.mean()


class AbstractGaussPdf(Pdf):
    r"""Abstract base for all Gaussian-like pdfs - the ones that take vector mean
    and matrix covariance parameters. Extends :class:`Pdf`.

    :var mu: mean value
    :type mu: 1D :class:`numpy.ndarray`
    :var R: covariance matrix
    :type R: 2D :class:`numpy.ndarray`

    You can modify object parameters only if you are absolutely sure that you
    pass allowable values - parameters are only checked once in constructor.
    """

    def __copy__(self):
        """Make a shallow copy of AbstractGaussPdf (or its derivative provided
        that is doesn't add class variables)"""
        # we cannont use AbstractGaussPdf statically - this method may be called
        # by derived class
        ret = type(self).__new__(type(self))  # TODO: currently slower than PY_NEW()
        ret.mu = self.mu
        ret.R = self.R
        ret.rv = self.rv
        ret.cond_rv = self.cond_rv
        return ret

    def __deepcopy__(self, memo):
        """Make a deep copy of AbstractGaussPdf (or its derivative provided
        that is doesn't add class variables)"""
        # we cannont use AbstractGaussPdf statically - this method may be called
        # by derived class
        ret = type(self).__new__(type(self))  # TODO: currently slower than PY_NEW()
        ret.mu = deepcopy(self.mu, memo)
        ret.R = deepcopy(self.R, memo)
        ret.rv = deepcopy(self.rv, memo)
        ret.cond_rv = deepcopy(self.cond_rv, memo)
        return ret


class GaussPdf(AbstractGaussPdf):
    r"""Unconditional Gaussian (normal) probability density function. Extends
    :class:`AbstractGaussPdf`.

    .. math:: f(x) \propto \exp \left( - \left( x-\mu \right)' R^{-1} \left( x-\mu \right) \right)
    """

    def __init__(self, mean, cov, rv = None):
        r"""Initialise Gaussian pdf.

        :param mean: mean value
        :type mean: 1D :class:`numpy.ndarray`
        :param cov: covariance matrix
        :type cov: 2D :class:`numpy.ndarray`

        To create standard normal distribution:

        >>> # note that cov is a matrix because of the double [[ and ]]
        >>> norm = GaussPdf(np.array([0.]), np.array([[1.]]))
        """
        if not isinstance(mean, ndarray):
            raise TypeError("mean must be numpy.ndarray")
        if not isinstance(cov, ndarray):
            raise TypeError("cov must be numpy.ndarray")
        if mean.ndim != 1:
            raise ValueError("mean must be one-dimensional (" + str(mean.ndim) + " dimensions encountered)")
        n = mean.shape[0]
        if cov.ndim != 2:
            raise ValueError("cov must be two-dimensional")
        if cov.shape[0] != n or cov.shape[1] != n:
            raise ValueError("cov must have shape (" + str(n) + ", " + str(n) + "), " +
                             str(cov.shape) + " given")
        if np_any(cov != cov.T):
            raise ValueError("cov must be symmetric (complex covariance not supported)")
        # TODO: covariance must be positive definite
        self.mu = mean
        self.R = cov
        self._set_rvs(rv, None)

    def shape(self):
        return self.mu.shape[0]

    def mean(self, cond = None):
        return self.mu

    def variance(self, cond = None):
        return diag(self.R)

    def eval_log(self, x, cond = None):
        self._check_x(x)

        # compute logarithm of normalization constant (TODO: can be cached in future)
        # log(2*Pi) = 1.83787706640935
        # we ignore sign (first part of slogdet return value) as it must be positive
        log_norm = -1/2. * (self.mu.shape[0]*1.83787706640935 + slogdet(self.R)[1])

        # part that actually depends on x
        log_val = -1/2. * dotvv(x - self.mu, dot(inv(self.R), x - self.mu))
        return log_norm + log_val  # = log(norm*val)

    def sample(self, cond = None):
        # TODO: in univariate case, random.normal() can be used directly
        z = random.normal(size=self.mu.shape[0]);
        # NumPy's cholesky(R) is equivalent to Matlab's chol(R).transpose()
        return self.mu + dot(cholesky(self.R), z);


class LogNormPdf(AbstractGaussPdf):
    r"""Unconditional log-normal probability density function. Extends
    :class:`AbstractGaussPdf`.

    More precisely, the density of random variable :math:`Y` where
    :math:`Y = exp(X); ~ X \sim \mathcal{N}(\mu, R)`
    """

    def __init__(self, mean, cov, rv = None):
        r"""Initialise log-normal pdf.

        :param mean: mean value of the **logarithm** of the associated random variable
        :type mean: 1D :class:`numpy.ndarray`
        :param cov: covariance matrix of the **logarithm** of the associated random variable
        :type cov: 2D :class:`numpy.ndarray`

        A current limitation is that LogNormPdf is only univariate. To create
        standard log-normal distribution:

        >>> lognorm = LogNormPdf(np.array([0.]), np.array([[1.]]))  # note the shape of covariance
        """
        if not isinstance(mean, ndarray):
            raise TypeError("mean must be numpy.ndarray")
        if not isinstance(cov, ndarray):
            raise TypeError("cov must be numpy.ndarray")
        if mean.ndim != 1:
            raise ValueError("mean must be one-dimensional (" + str(mean.ndim) + " dimensions encountered)")
        n = mean.shape[0]
        if n != 1:
            raise ValueError("LogNormPdf is currently limited to univariate random variables")
        if cov.ndim != 2:
            raise ValueError("cov must be two-dimensional")
        if cov.shape[0] != n or cov.shape[1] != n:
            raise ValueError("cov must have shape (" + str(n) + ", " + str(n) + "), " +
                             str(cov.shape) + " given")
        if cov[0,0] <= 0.:
            raise ValueError("cov must be positive")
        self.mu = mean
        self.R = cov
        self._set_rvs(rv, None)

    def shape(self):
        return 1

    def mean(self, cond = None):
        return exp(self.mu + self.R[0]/2.)

    def variance(self, cond = None):
        return (exp(self.R[0])[0] - 1.)*exp(2*self.mu + self.R[0])

    def eval_log(self, x, cond = None):
        self._check_x(x)
        if x[0] <= 0:  # log-normal pdf support = (0, +inf)
            return float('-inf')

        # 1/2.*log(2*pi) = 0.91893853320467
        return -((log(x[0]) - self.mu[0])**2)/(2.*self.R[0,0]) - log(x[0]*sqrt(self.R[0,0])) - 0.91893853320467

    def sample(self, cond = None):
        # size parameter ( = 1) makes lognormal() return a ndarray
        return random.lognormal(self.mu[0], sqrt(self.R[0,0]), 1)


class AbstractEmpPdf(Pdf):
    r"""An abstraction of empirical probability density functions that provides common methods such
    as weight normalisation. Extends :class:`Pdf`.

    :var numpy.ndarray weights: 1D array of particle weights
       :math:`\omega_i >= 0 \forall i; \quad \sum \omega_i = 1`
    """

    def normalise_weights(self):
        r"""Multiply weights by appropriate constant so that :math:`\sum \omega_i = 1`

        :raise AttributeError: when :math:`\exists i: \omega_i < 0` or
           :math:`\forall i: \omega_i = 0`
        """
        if np_any(self.weights < 0.):
            raise AttributeError("Weights must not be negative")
        wsum = sum(self.weights)
        if wsum == 0:
            raise AttributeError("Sum of weights == 0: weights cannot be normalised")
        self.weights *= 1./wsum
        return True

    def get_resample_indices(self):
        r"""Calculate first step of resampling process (dropping low-weight particles and replacing
        them with more weighted ones.

        :return: integer array of length n: :math:`(a_1, a_2 \dots a_n)` where :math:`a_i` means
           that particle at ith place should be replaced with particle number :math:`a_i`
        :rtype: :class:`numpy.ndarray` of ints

        *This method doesnt modify underlying pdf in any way - it merely calculates how particles
        should be replaced.*
        """
        n = self.weights.shape[0]
        cum_weights = cumsum(self.weights)

        u = (arange(n, dtype=float) + random.uniform()) / n
        # u[i] = (i + fuzz) / n

        # calculate number of babies for each particle
        baby_indeces = zeros(n, dtype=int)  # index array: a[i] contains index of
        # original particle that should be at i-th place in new particle array
        j = 0
        for i in range(n):
            while u[i] > cum_weights[j]:
                j += 1
            baby_indeces[i] = j
        return baby_indeces


class EmpPdf(AbstractEmpPdf):
    r"""Weighted empirical probability density function. Extends :class:`AbstractEmpPdf`.

    .. math::

       p(x) &= \sum_{i=1}^n \omega_i \delta(x - x^{(i)}) \\
       \text{where} \quad x^{(i)} &\text{ is value of the i}^{th} \text{ particle} \\
       \omega_i \geq 0 &\text{ is weight of the i}^{th} \text{ particle} \quad \sum \omega_i = 1

    :var numpy.ndarray particles: 2D array of particles; shape: (n, m) where n
       is the number of particles, m dimension of this pdf

    You may alter particles and weights, but you must ensure that their shapes
    match and that weight constraints still hold. You can use
    :meth:`~AbstractEmpPdf.normalise_weights` to do some work for you.
    """

    def __init__(self, init_particles, rv = None):
        r"""Initialise empirical pdf.

        :param init_particles: 2D array of initial particles; shape (*n*, *m*)
           determines that *n* *m*-dimensioned particles will be used. *Warning:
           EmpPdf does not copy the particles - it rather uses passed array
           through its lifetime, so it is not safe to reuse it for other
           purposes.*
        :type init_particles: :class:`numpy.ndarray`
        """
        if not isinstance(init_particles, ndarray) or init_particles.ndim != 2:
            raise TypeError("init_particles must be 2D numpy.ndarray")
        self.particles = init_particles
        # set n weights to 1/n
        self.weights = ones(self.particles.shape[0]) / self.particles.shape[0]

        self._set_rvs(rv, None)

    def shape(self):
        return self.particles.shape[1]

    def mean(self, cond = None):
        ret = zeros(self.particles.shape[1])
        for i in range(self.particles.shape[0]):
            ret += self.weights[i] * self.particles[i]
        return ret

    def variance(self, cond = None):
        ret = zeros(self.particles.shape[1])
        for i in range(self.particles.shape[0]):
            ret += self.weights[i] * self.particles[i]**2
        return ret - self.mean()**2

    def eval_log(self, x, cond = None):
        raise NotImplementedError("eval_log doesn't make sense for discrete distribution")

    def sample(self, cond = None):
        raise NotImplementedError("Sample for empirical pdf not (yet?) implemented")

    def resample(self):
        """Drop low-weight particles, replace them with copies of more weighted
        ones. Also reset weights to uniform."""
        self.particles = self.particles[self.get_resample_indices()]
        self.weights[:] = 1./self.weights.shape[0]
        return True


class MarginalizedEmpPdf(AbstractEmpPdf):
    r"""An extension to empirical pdf (:class:`EmpPdf`) used as aposteriori density by
    :class:`~pybayes.filters.MarginalizedParticleFilter`. Extends :class:`AbstractEmpPdf`.

    Assume that random variable :math:`x` can be divided into 2 independent
    parts :math:`x = [a, b]`, then probability density function can be written as

    .. math::

       p &= \sum_{i=1}^n \omega_i \Big[ \mathcal{N}\left(\hat{a}^{(i)}, P^{(i)}\right) \Big]_a
       \delta(b - b^{(i)}) \\
       \text{where } \quad \hat{a}^{(i)} &\text{ and } P^{(i)} \text{ is mean and
       covariance of i}^{th} \text{ gauss pdf} \\
       b^{(i)} &\text{ is value of the (second part of the) i}^{th} \text{ particle} \\
       \omega_i \geq 0 &\text{ is weight of the i}^{th} \text{ particle} \quad \sum \omega_i = 1

    :var numpy.ndarray gausses: 1D array that holds :class:`GaussPdf`
       for each particle; shape: (n) where n is the number of particles
    :var numpy.ndarray particles: 2D array of particles; shape: (n, m) where n
       is the number of particles, m dimension of the "empirical" part of random variable
    :var numpy.ndarray weights: 1D array of particle weights

    You may alter particles and weights, but you must ensure that their shapes
    match and that weight constraints still hold. You can use
    :meth:`~AbstractEmpPdf.normalise_weights` to do some work for you.

    *Note: this pdf could have been coded as ProdPdf of EmpPdf and a mixture of GaussPdfs. However
    it is implemented explicitly for simplicity and speed reasons.*
    """

    def __init__(self, init_gausses, init_particles, rv = None):
        r"""Initialise marginalized empirical pdf.

        :param init_gausses: 1D array of :class:`GaussPdf` objects, all must have
           the dimension
        :type init_gausses: :class:`numpy.ndarray`
        :param init_particles: 2D array of initial particles; shape (*n*, *m*)
           determines that *n* particles whose *empirical* part will have dimension *m*
        :type init_particles: :class:`numpy.ndarray`

        *Warning: MarginalizedEmpPdf does not copy the particles - it rather uses
        both passed arrays through its lifetime, so it is not safe to reuse them
        for other purposes.*
        """
        if not isinstance(init_gausses, ndarray) or init_gausses.ndim != 1:
            raise TypeError("init_gausses must be 1D numpy.ndarray")
        if not isinstance(init_particles, ndarray) or init_particles.ndim != 2:
            raise TypeError("init_particles must be 2D numpy.ndarray")
        if init_gausses.shape[0] != init_particles.shape[0] or init_gausses.shape[0] < 1:
            raise ValueError("init_gausses count must be same as init_particles count and both must be positive")
        gauss_shape = 0
        for gauss in init_gausses:
            if not isinstance(gauss, GaussPdf):
                raise TypeError("all init_gausses items must be (subclasses of) GaussPdf")
            if gauss_shape == 0:
                gauss_shape = gauss.shape()  # guaranteed to be non-zero
            elif gauss.shape() != gauss_shape:
                raise ValueError("all init_gausses items must have same shape")

        self.gausses = init_gausses
        self.particles = init_particles
        # set n weights to 1/n
        self.weights = ones(self.particles.shape[0]) / self.particles.shape[0]
        self._gauss_shape = self.gausses[0].shape()  # shape of the gaussian component
        self._part_shape = self.particles.shape[1]  # shape of the empirical component

        self._set_rvs(rv, None)

    def shape(self):
        return self._gauss_shape + self._part_shape

    def mean(self, cond = None):
        ret = zeros(self.shape())
        temp = empty(self.shape())
        for i in range(self.particles.shape[0]):
            temp[0:self._gauss_shape] = self.gausses[i].mean()
            temp[self._gauss_shape:] = self.particles[i]
            ret += self.weights[i] * temp
        return ret

    def variance(self, cond = None):
        # first, compute 2nd non-central moment
        mom2 = zeros(self.shape())
        temp = empty(self.shape())

        for i in range(self.particles.shape[0]):
            # set gauss part of temp to \mu_i^2 + \sigma_i^2
            temp[0:self._gauss_shape] = self.gausses[i].mean()**2 + self.gausses[i].variance()**2
            # set empirical part of temp to x_i^2
            temp[self._gauss_shape:] = self.particles[i]**2

            # finaly scale by \omega_i and add to 2nd non-central moment we are computing
            mom2 += self.weights[i] * temp  # cython limitation: cannot compile: array_a[0:n] += array_b

        # return 2nd central moment by subtracting square of mean value
        return mom2 - self.mean()**2

    def eval_log(self, x, cond = None):
        raise NotImplementedError("eval_log doesn't make sense for (partially) discrete distribution")

    def sample(self, cond = None):
        raise NotImplementedError("Drawing samples from MarginalizesEmpPdf is not supported")


class ProdPdf(Pdf):
    r"""Unconditional product of multiple unconditional pdfs.

    You can for example create a pdf that has uniform distribution with regards
    to x-axis and normal distribution along y-axis. The caller (you) must ensure
    that individial random variables are independent, otherwise their product may
    have no mathematical sense. Extends :class:`Pdf`.

    .. math:: f(x_1 x_2 x_3) = f_1(x_1) f_2(x_2) f_3(x_3)
    """

    def __init__(self, factors, rv = None):
        r"""Initialise product of unconditional pdfs.

        :param factors: sequence of sub-distributions
        :type factors: sequence of :class:`Pdf`

        As an exception from the general rule, ProdPdf does not create anonymous
        associated random variable if you do not supply it in constructor - it
        rather reuses components of underlying factor pdfs. (You can of course
        override this behaviour by bassing custom **rv**.)

        Usual way of creating ProdPdf could be:

        >>> prod = ProdPdf((UniPdf(...), GaussPdf(...)))  # note the double (( and ))
        """
        if rv is None:
            rv_comps = []  # prepare to construnct associated rv
        else:
            rv_comps = None

        if len(factors) is 0:
            raise ValueError("at least one factor must be passed")
        self.factors = array(factors, dtype=Pdf)
        self.shapes = zeros(self.factors.shape[0], dtype=int)  # array of factor shapes
        for i in range(self.factors.shape[0]):
            if not isinstance(self.factors[i], Pdf):
                raise TypeError("all records in factors must be (subclasses of) Pdf")
            self.shapes[i] = self.factors[i].shape()
            if rv_comps is not None:
                rv_comps.extend(self.factors[i].rv.components)  # add components of child rvs

        # pre-calclate shape
        self._shape = sum(self.shapes)
        # associate with a rv (needs to be after _shape calculation)
        if rv_comps is None:
            self._set_rvs(rv, None)
        else:
            self._set_rvs(RV(*rv_comps), None)

    def shape(self):
        return self._shape

    def mean(self, cond = None):
        curr = 0
        ret = zeros(self.shape())
        for i in range(self.factors.shape[0]):
            ret[curr:curr + self.shapes[i]] = self.factors[i].mean()
            curr += self.shapes[i]
        return ret;

    def variance(self, cond = None):
        curr = 0
        ret = zeros(self.shape())
        for i in range(self.factors.shape[0]):
            ret[curr:curr + self.shapes[i]] = self.factors[i].variance()
            curr += self.shapes[i]
        return ret;

    def eval_log(self, x, cond = None):
        self._check_x(x)

        curr = 0
        ret = 0.  # 1 is neutral element in multiplication; log(1) = 0
        for i in range(self.factors.shape[0]):
            ret += self.factors[i].eval_log(x[curr:curr + self.shapes[i]])  # log(x*y) = log(x) + log(y)
            curr += self.shapes[i]
        return ret;

    def sample(self, cond = None):
        curr = 0
        ret = zeros(self.shape())
        for i in range(self.factors.shape[0]):
            ret[curr:curr + self.shapes[i]] = self.factors[i].sample()
            curr += self.shapes[i]
        return ret;


class MLinGaussCPdf(CPdf):
    r"""Conditional Gaussian pdf whose mean is a linear function of condition.
    Extends :class:`CPdf`.

    .. math::

       f(x|c) \propto \exp \left( - \left( x-\mu \right)' R^{-1} \left( x-\mu \right) \right)
       \quad \quad \text{where} ~ \mu := A c + b
    """

    def __init__(self, cov, A, b, rv = None, cond_rv = None, base_class = None):
        r"""Initialise Mean-Linear Gaussian conditional pdf.

        :param cov: covariance of underlying Gaussian pdf
        :type cov: 2D :class:`numpy.ndarray`
        :param A: given condition :math:`c`, :math:`\mu = Ac + b`
        :type A: 2D :class:`numpy.ndarray`
        :param b: see above
        :type b: 1D :class:`numpy.ndarray`
        :param class base_class: class whose instance is created as a base pdf for this
           cpdf. Must be a subclass of :class:`AbstractGaussPdf` and the default is
           :class:`GaussPdf`. One alternative is :class:`LogNormPdf` for example.
        """
        if base_class is None:
            self.gauss = GaussPdf(zeros(cov.shape[0]), cov)
        else:
            if not issubclass(base_class, AbstractGaussPdf):
                raise TypeError("base_class must be a class (not an instance) and subclass of AbstractGaussPdf")
            self.gauss = base_class(zeros(cov.shape[0]), cov)

        self.A = asarray(A)
        self.b = asarray(b)
        if self.A.ndim != 2:
            raise ValueError("A must be 2D numpy.ndarray (matrix)")
        if self.b.ndim != 1:
            raise ValueError("b must be 1D numpy.ndarray (vector)")
        if self.b.shape[0] != self.gauss.shape():
            raise ValueError("b must have same number of cols as covariance")
        if self.A.shape[0] != self.b.shape[0]:
            raise ValueError("A must have same number of rows as covariance")
        self._set_rvs(rv, cond_rv)

    def shape(self):
        return self.b.shape[0]

    def cond_shape(self):
        return self.A.shape[1]

    def mean(self, cond = None):
        # note: it may not be true that gauss.mu == gauss.mean() for all AbstractGaussPdf
        # classes. One such example is LogNormPdf
        self._set_mean(cond)
        return self.gauss.mean()

    def variance(self, cond = None):
        # note: for some AbstractGaussPdf variance may depend on mu
        self._set_mean(cond)
        return self.gauss.variance()

    def eval_log(self, x, cond = None):
        # x is checked in self.gauss
        self._set_mean(cond)
        return self.gauss.eval_log(x)

    def sample(self, cond = None):
        self._set_mean(cond)
        return self.gauss.sample()

    def _set_mean(self, cond):
        self._check_cond(cond)
        self.gauss.mu = dot(self.A, cond)
        self.gauss.mu += self.b
        return True


class LinGaussCPdf(CPdf):
    r"""Conditional one-dimensional Gaussian pdf whose mean and covariance are
    linear functions of condition. Extends :class:`CPdf`.

    .. math::

       f(x|c_1 c_2) \propto \exp \left( - \frac{\left( x-\mu \right)^2}{2\sigma^2} \right)
       \quad \quad \text{where} \quad \mu := a c_1 + b \quad \text{and}
       \quad \sigma^2 := c c_2 + d
    """

    def __init__(self, a, b, c, d, rv = None, cond_rv = None, base_class = None):
        r"""Initialise Linear Gaussian conditional pdf.

        :param double a, b: mean = a*cond_1 + b
        :param double c, d: covariance = c*cond_2 + d
        :param class base_class: class whose instance is created as a base pdf for this
           cpdf. Must be a subclass of :class:`AbstractGaussPdf` and the default is
           :class:`GaussPdf`. One alternative is :class:`LogNormPdf` for example.
        """
        if not isinstance(a, float):
            raise TypeError("all parameters must be floats")
        self.a = a
        if not isinstance(b, float):
            raise TypeError("all parameters must be floats")
        self.b = b
        if not isinstance(c, float):
            raise TypeError("all parameters must be floats")
        self.c = c
        if not isinstance(d, float):
            raise TypeError("all parameters must be floats")
        self.d = d
        if base_class is None:
            self.gauss = GaussPdf(zeros(1), array([[1.]]))
        else:
            if not issubclass(base_class, AbstractGaussPdf):
                raise TypeError("base_class must be a class (not an instance) and subclass of AbstractGaussPdf")
            self.gauss = base_class(zeros(1), array([[1.]]))
        self._set_rvs(rv, cond_rv)

    def shape(self):
        return 1

    def cond_shape(self):
        return 2

    def mean(self, cond = None):
        self._set_gauss_params(cond)
        return self.gauss.mean()

    def variance(self, cond = None):
        self._set_gauss_params(cond)
        return self.gauss.variance()

    def eval_log(self, x, cond = None):
        self._set_gauss_params(cond)
        # x is checked in self.gauss.eval_log()
        return self.gauss.eval_log(x)

    def sample(self, cond = None):
        self._set_gauss_params(cond)
        return self.gauss.sample()

    def _set_gauss_params(self, cond):
        self._check_cond(cond)
        c0 = cond[0]  # workaround for cython limitation: no buffer type in pure python mode
        c1 = cond[1]
        self.gauss.mu[0] = self.a*c0 + self.b
        self.gauss.R[0,0] = self.c*c1 + self.d
        return True


class GaussCPdf(CPdf):
    r"""The most general normal conditional pdf. Use it only if you cannot use
    :class:`MLinGaussCPdf` or :class:`LinGaussCPdf` as this cpdf is least
    optimised. Extends :class:`CPdf`.

    .. math::

       f(x|c) &\propto \exp \left( - \left( x-\mu \right)' R^{-1} \left( x-\mu \right) \right) \\
       \text{where} \quad \mu &:= f(c) \text{ (interpreted n-dimensional vector)} \\
       R &:= g(c) \text{ (interpreted as n*n matrix)}
    """

    def __init__(self, shape, cond_shape, f, g, rv = None, cond_rv = None, base_class = None):
        r"""Initialise general gauss cpdf.

        :param int shape: dimension of random vector
        :param int cond_shape: dimension of condition
        :param callable f: :math:`\mu := f(c)` where c = condition
        :param callable g: :math:`R := g(c)` where c = condition
        :param class base_class: class whose instance is created as a base pdf for this
           cpdf. Must be a subclass of :class:`AbstractGaussPdf` and the default is
           :class:`GaussPdf`. One alternative is :class:`LogNormPdf` for example.

        TODO: better specification of callback functions
        """
        self._shape = shape
        self._cond_shape = cond_shape
        self.f = f
        self.g = g
        if base_class is None:
            # TODO: to be correct, np.eye would be needed
            self.gauss = GaussPdf(zeros(self._shape), ones((self._shape, self._shape)))
        else:
            if not issubclass(base_class, AbstractGaussPdf):
                raise TypeError("base_class must be a class (not an instance) and subclass of AbstractGaussPdf")
            self.gauss = base_class(zeros(self._shape), ones((self._shape, self._shape)))
        self._set_rvs(rv, cond_rv)

    def shape(self):
        return self._shape

    def cond_shape(self):
        return self._cond_shape

    def mean(self, cond = None):
        self._set_gauss_params(cond)
        return self.gauss.mean()

    def variance(self, cond = None):
        self._set_gauss_params(cond)
        return self.gauss.variance()

    def eval_log(self, x, cond = None):
        self._set_gauss_params(cond)
        # x is checked in self.gauss
        return self.gauss.eval_log(x)

    def sample(self, cond = None):
        self._set_gauss_params(cond)
        return self.gauss.sample()

    def _set_gauss_params(self, cond):
        self._check_cond(cond)
        self.gauss.mu = self.f(cond).reshape(self._shape)
        self.gauss.R = self.g(cond).reshape((self._shape, self._shape))
        return True


class ProdCPdf(CPdf):
    r"""Pdf that is formed as a chain rule of multiple conditional pdfs.
    Extends :class:`CPdf`.

    TODO: make aggreate [cond\_]rv construction automatic and drop old constuctor.

    In a
    simple textbook case denoted below it isn't needed to specify random variables
    at all. In this case when no random variable associations are passed,
    ProdCPdf ignores rv associations of its factors and everything is determined
    from their order. (:math:`x_i` are arbitrary vectors)

    .. math::

        f(x_1 x_2 x_3 | c) &= f_1(x_1 | x_2 x_3 c) f_2(x_2 | x_3 c) f_3(x_3 | c) \\
        \text{or} \quad f(x_1 x_2 x_3) &= f_1(x_1 | x_2 x_3) f_2(x_2 | x_3) f_3(x_3)

    >>> f = ProdCPdf((f1, f2, f3))

    For less simple situations, specifiying random value associations is needed
    to estabilish data chain:

    .. math:: p(x_1 x_2 | y_1 y_2) = p_1(x_1 | x_2) p_2(x_2 | y_2 y_1)

    >>> # prepare random variable components:
    >>> x_1, x_2 = RVComp(1), RVComp(1, "name is optional")
    >>> y_1, y_2 = RVComp(1), RVComp(1, "but recommended")

    >>> p_1 = SomePdf(..., rv=RV(x_1), cond_rv=RV(x_2))
    >>> p_2 = SomePdf(..., rv=RV(x_2), cond_rv=RV(y_2, y_1))
    >>> p = ProdCPdf((p_2, p_1), rv=RV(x_1, x_2), cond_rv=RV(y_1, y_2))  # order of
    >>> # pdfs is insignificant - order of rv components determines data flow
    """

    def __init__(self, factors, rv = None, cond_rv = None):
        """Construct chain rule of multiple cpdfs.

        :param factors: sequence of densities that will form the product
        :type factors: sequence of :class:`CPdf`

        Usual way of creating ProdCPdf could be:

        >>> prod = ProdCPdf((MLinGaussCPdf(..), UniPdf(..)), RV(..), RV(..))
        """
        if len(factors) is 0:
            raise ValueError("at least one factor must be passed")

        self.in_indeces = []  # data link representations
        self.out_indeces = []

        if rv is None and cond_rv is None:
            self._init_anonymous(factors)
        elif rv is not None and cond_rv is not None:
            self._init_with_rvs(list(factors), rv, cond_rv)  # needs factors as list
        else:
            raise AttributeError("Please pass both rv and cond_rv or none of them, other combinations not (yet) supported")

        self._set_rvs(rv, cond_rv)

    def _init_anonymous(self, factors):
        self.factors = array(factors, dtype=CPdf)

        # overall cond shape equals last factor cond shape:
        self._cond_shape = factors[-1].cond_shape()
        self._shape = factors[0].shape() + factors[0].cond_shape() - self._cond_shape

        start_ind = 0  # current start index in cummulate rv and cond_rv data array
        for i in range(self.factors.shape[0]):
            factor = self.factors[i]
            if not isinstance(factor, CPdf):
                raise TypeError("all records in factors must be (subclasses of) CPdf")

            shape = factor.shape()
            cond_shape = factor.cond_shape()
            # expected (normal + cond) shape:
            exp_shape = self._shape + self._cond_shape - start_ind
            if shape + cond_shape != exp_shape:
                raise ValueError("Expected that pdf {0} will have shape (={1}) + ".
                    format(factor, shape) + "cond_shape (={0}) == {1}".
                    format(cond_shape, exp_shape))

            self.in_indeces.append(arange(start_ind + shape, start_ind + shape + cond_shape))
            self.out_indeces.append(arange(start_ind, start_ind + shape))

            start_ind += shape

        if start_ind != self._shape:
            raise ValueError("Shapes do not match")

    def _init_with_rvs(self, factors, rv, cond_rv):
        """Initialise ProdCPdf using rv components for data chain construction.

        :param factors: factor pdfs that will form the product
        :type factors: :class:`list` of :class:`CPdf` items
        """
        # gradually filled set of components that would be available in e.g.
        # sample() computation:
        avail_rvcomps = set(cond_rv.components)

        self.factors = empty(len(factors), dtype=CPdf)  # initialise factor array

        i = self.factors.shape[0] - 1  # factors are filled from right to left
        # iterate until all input pdfs are processed
        while len(factors) > 0:
            # find next pdf that can be added to data chain (all its cond
            # components can be already computed)
            for j in range(len(factors)):
                factor = factors[j]
                if not isinstance(factor, CPdf):
                    raise TypeError("all records in factors must be (subclasses of) CPdf")
                if factor.cond_rv.contained_in(avail_rvcomps):
                    # one such pdf found
                    #DEBUG: print "Appropriate pdf found:", factor, "with rv:", factor.rv, "and cond_rv:", factor.cond_rv
                    if not rv.contains_all(factor.rv.components):
                        raise AttributeError(("Some of {0}'s associated rv components "
                            + "({1}) aren't present in rv ({2})").format(factor, factor.rv, rv))
                    avail_rvcomps.update(factor.rv.components)
                    self.factors[i] = factor
                    i += -1
                    del factors[j]
                    break;
            else:
                # we are stuck somewhere in data chain
                print "Appropriate pdf not found. avail_rvcomps:", avail_rvcomps, "candidates:"
                for factor in factors:
                    print "  ", factor, "with cond_rv:", factor.cond_rv
                raise AttributeError("Cannont construct data chain. This means "
                    + "that it is impossible to arrange factor pdfs into a DAG "
                    + "that starts with ProdCPdf's cond_rv components. Please "
                    + "check cond_rv and factor rvs and cond_rvs.")
        if not rv.contained_in(avail_rvcomps):
            print "These components can be computed:", avail_rvcomps
            print "... but we have to fill following rv:", rv
            raise AttributeError("Data chain built, some components cannot be "
                + "computed with it.")

        cummulate_rv = RV(rv, cond_rv)
        for i in range(self.factors.shape[0]):
            factor = self.factors[i]
            self.in_indeces.append(factor.cond_rv.indexed_in(cummulate_rv))
            self.out_indeces.append(factor.rv.indexed_in(cummulate_rv))

        self._shape = rv.dimension
        self._cond_shape = cond_rv.dimension

    def shape(self):
        return self._shape

    def cond_shape(self):
        return self._cond_shape

    def mean(self, cond = None):
        raise NotImplementedError("Not yet implemented")

    def variance(self, cond = None):
        raise NotImplementedError("Not yet implemented")

    def eval_log(self, x, cond = None):
        self._check_x(x)
        self._check_cond(cond)

        # combination of evaluation point and condition:
        data = empty(self._shape + self._cond_shape)
        data[0:self._shape] = x
        data[self._shape:] = cond
        ret = 0.

        for i in range(self.factors.shape[0]):
            ret += self.factors[i].eval_log(data[self.out_indeces[i]], data[self.in_indeces[i]])
        return ret

    def sample(self, cond = None):
        self._check_cond(cond)

        # combination of sampled variables and condition:
        data = empty(self._shape + self._cond_shape)
        data[self._shape:] = cond  # rest is undefined

        # process pdfs from right to left (they are arranged so that data flow
        # is well defined in this case):
        for i in range(self.factors.shape[0] -1, -1, -1):
            data[self.out_indeces[i]] = self.factors[i].sample(data[self.in_indeces[i]])

        return data[:self._shape]  # return right portion of data
