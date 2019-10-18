import numpy as np
import scipy.stats as st
from scipy import integrate
from scipy.special import erf, erfinv
import matplotlib.pyplot as plt
from statsmodels.distributions.empirical_distribution import ECDF


class Gamma(st.rv_continuous):
    domain = [1e-8, 5]

    def _pdf(self, x):
        return 1 / (np.sqrt(np.pi * x)) * np.exp(-x)

    def _cdf(self, x):
        return erf(np.sqrt(x))

    def _ppf(self, x):
        return erfinv(x)**2

    def rvs(self, size):
        x = np.random.uniform(0, 1, size)

        return self._ppf(x)


class TwoGaussians(st.rv_continuous):
    distributions = [st.norm(5, 3),
                     st.norm(0, 0.5)]
    weights = [0.93, .07]

    def _pdf(self, x):
        result = 0
        for weight, distr in zip(TwoGaussians.weights, TwoGaussians.distributions):
            result += weight * distr.pdf(x)
        return result

    def rvs(self, size):
        mixture_idx = np.random.choice(len(TwoGaussians.weights), size=size, replace=True, p=TwoGaussians.weights)
        # y is the mixture sample
        y = np.fromiter((TwoGaussians.distributions[i].rvs() for i in mixture_idx), dtype=np.float64)
        return y


class FiveFingers(st.rv_continuous):
    w = 0.5
    distributions = [st.norm(1/10, 1/100),
                     st.norm(3/10, 1/100),
                     st.norm(5/10, 1/100),
                     st.norm(7/10, 1/100),
                     st.norm(9/10, 1/100)]

    weights = [1/len(distributions)] * len(distributions)
    domain = [0, 1]

    def _pdf(self, x):
        def summation():
            result = 0
            for weight, distr in zip(FiveFingers.weights, FiveFingers.distributions):
                result += weight * distr.pdf(x)
            return result
        return summation()

    def _cdf(self, x):
        def summation():
            result = 0
            for weight, distr in zip(FiveFingers.weights, FiveFingers.distributions):
                result += weight * distr.cdf(x)
            return result
        return summation()

    # def _ppf(self, x):
    #     """
    #     Inverse of cdf
    #     """
    #     def summation():
    #         result = 0
    #         for weight, distr in zip(FiveFingers.weights, FiveFingers.distributions):
    #             result += weight * distr.ppf(x)
    #         return result
    #
    #     #return FiveFingers.w * summation() - (1/FiveFingers.w)*(1 - FiveFingers.w)
    #     return summation()

    def rvs(self, size):
        mixture_idx = np.random.choice(len(FiveFingers.weights), size=size, replace=True, p=FiveFingers.weights)
        # y is the mixture sample
        y = np.fromiter((FiveFingers.distributions[i].rvs() for i in mixture_idx), dtype=np.float64)
        return y


class Cauchy(st.rv_continuous):

    def _pdf(self, x):
        return 1.0 / np.pi / (1.0 + x * x)

    def _cdf(self, x):
        return 0.5 + 1.0 / np.pi * np.arctan(x)

    def _ppf(self, q):
        return np.tan(np.pi * q - np.pi / 2.0)

    def rvs(self, size):
        x = np.random.uniform(0, 1, size)
        return self._ppf(x)


# class Discontinous(st.rv_continuous):
#     def _pdf(self):
#         pass

# def test_cauchy():
#     beta = 0.5
#     g = Cauchy()
#
#     vals = g.ppf([0.001, 0.5, 0.999])
#     assert np.allclose([0.001, 0.5, 0.999], g.cdf(vals))
#     assert np.isclose(integrate.quad(g.pdf, 0, np.inf)[0], 1)
#
#     x = np.linspace(1e-5, 7, 200)
#     print("type x ", type(x))
#
#     # g = st.lognorm(1)
#
#     print("g.cdf(2) - g.cdf(1) ", g.cdf(20) - g.cdf(0.1))
#     print("pdf ", integrate.quad(g.pdf, 0.1, 20)[0])
#
#     x = np.array([1.0, 2.0])

def test_two_gaussians():
    tg = TwoGaussians()

    assert np.isclose(integrate.quad(tg._pdf, -np.inf, np.inf)[0], 1)

    # x = np.linspace(0, 1, 100000)
    # plt.plot(x, ff.cdf(x), label="cdf")
    # plt.plot(x, ff.ppf(x), "r-", label="ppf")
    # plt.legend()
    # plt.ylim(-0.5, 4)
    # plt.xlim(-0.1, 1)
    # plt.show()

    a = np.random.uniform(-5, 20, 1)
    b = np.random.uniform(-5, 20, 1)
    assert np.isclose(tg.cdf(b) - tg.cdf(a), integrate.quad(tg.pdf, a, b)[0])

    size = 100000
    values = tg.rvs(size=size)
    x = np.linspace(-10, 20, size)
    plt.plot(x, tg.pdf(x), 'r-', alpha=0.6, label='two gaussians pdf')
    plt.hist(values, bins=1000, density=True, alpha=0.2)
    plt.xlim(-10, 20)
    plt.legend()
    plt.show()


def test_five_fingers():
    ff = FiveFingers()

    assert np.isclose(integrate.quad(ff.pdf, 0, 1)[0], 1)
    a = 0.1
    b = 0.7
    assert np.isclose(ff.cdf(b) - ff.cdf(a), integrate.quad(ff.pdf, a, b)[0])

    values = ff.rvs(size=10000)
    x = np.linspace(0, 1, 10000)
    plt.plot(x, ff.pdf(x), 'r-', alpha=0.6, label='five fingers pdf')
    plt.hist(values, bins=100, density=True, alpha=0.2)
    plt.xlim(-1, 1)
    plt.legend()
    plt.show()

    from statsmodels.distributions.empirical_distribution import ECDF
    ecdf = ECDF(values)
    plt.plot(x, ecdf(x), label="ECDF")
    plt.plot(x, ff.cdf(x), label="exact cumulative distr function")
    plt.show()


def test_gamma():
    gamma = Gamma()

    x = np.linspace(0, 3, 100000)
    plt.plot(x, gamma.cdf(x), label="cdf")
    plt.plot(x, gamma.ppf(x), "r-", label="ppf")
    plt.legend()
    plt.ylim(-0.5, 4)
    plt.xlim(-0.1, 3)
    plt.show()

    a = 0.1
    b = 20

    vals = gamma.ppf([0.001, 0.5, 0.999])
    assert np.allclose([0.001, 0.5, 0.999], gamma.cdf(vals))
    assert np.isclose(gamma.cdf(b) - gamma.cdf(a), integrate.quad(gamma.pdf, a, b)[0])

    values = gamma.rvs(size=10000)
    x = np.linspace(gamma.ppf(0.001), gamma.ppf(0.999), 100000)
    plt.plot(x, gamma.pdf(x), 'r-', lw=5, alpha=0.6, label='gamma pdf')

    plt.hist(values, density=True, alpha=0.2)
    plt.xlim(-15, 15)
    plt.legend()
    plt.show()

    x = np.linspace(0, 5, 100000)
    ecdf = ECDF(values)
    plt.plot(x, ecdf(x), label="ECDF")
    plt.plot(x, gamma.cdf(x), label="exact cumulative distr function")
    plt.legend()
    plt.show()


def test_cauchy():
    cauchy = Cauchy()
    x = np.linspace(-2 * np.pi, 2 * np.pi, 10000)

    vals = cauchy.ppf([0.001, 0.5, 0.999])
    assert np.allclose([0.001, 0.5, 0.999], cauchy.cdf(vals))
    assert np.isclose(integrate.quad(cauchy.pdf, -np.inf, np.inf)[0], 1)

    plt.plot(x, cauchy.cdf(x), label="cdf")
    plt.plot(x, cauchy.ppf(x), "r-", label="ppf")
    plt.legend()
    plt.ylim(-5, 5)
    plt.show()

    a = 0.1
    b = 20
    vals = cauchy.ppf([0.001, 0.5, 0.999])
    assert np.allclose([0.001, 0.5, 0.999], cauchy.cdf(vals))
    assert np.isclose(cauchy.cdf(b) - cauchy.cdf(a), integrate.quad(cauchy.pdf, a, b)[0])

    values = cauchy.rvs(size=10000)
    x = np.linspace(cauchy.ppf(0.01), cauchy.ppf(0.99), 100000)
    plt.plot(x, cauchy.pdf(x), 'r-', lw=5, alpha=0.6, label='cauchy pdf')

    plt.hist(values, density=True, alpha=0.2)
    plt.xlim(-15, 15)
    plt.legend()
    plt.show()


if __name__ == "__main__":
    #test_cauchy()
    #test_gamma()
    #test_five_fingers()
    test_two_gaussians()
