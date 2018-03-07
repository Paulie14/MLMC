import time as t
from src.mlmc.flow_sim_generic import FlowSimGeneric as Sim
#from src.mlmc.simulation import Simulation as Sim
import math
from test.result import Result
from src.mlmc.mlmc import MLMC
from src.mlmc.moments import Monomials
from src.mlmc.moments import FourierFunctions
import scipy as sc
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.distributions.empirical_distribution import ECDF
from src.mlmc.distribution import Distribution


class Main:
    """
    Class launchs MLMC
    """
    def main(*args):
        pocet_urovni = 2
        pocet_vykonani = 1
        moments_number = 5
        bounds = [0, 2]
        toleration = 1e-15
        eps = 1e-10

        sim = Sim()
        sim.sim_param_range = (10, 100)

        result = Result(moments_number)
        result.levels_number = pocet_urovni
        result.execution_number = pocet_vykonani

        function = mo = Monomials(moments_number)

        for i in range(pocet_vykonani):
            mo.eps = eps
            result = Result(moments_number)
            result.levels_number = pocet_urovni
            result.execution_number = pocet_vykonani
            start_MC = t.time()
            moments_object = mo
            # number of levels, n_fine, n_coarse, simulation
            m = MLMC(pocet_urovni, sim, moments_object)

            # Exact number of simulation on each level
            #m.number_of_simulations = [10000, 500, 100]

            # type, time or variance
            variance = [1e-5, 1e-3, 1e-3, 1e-3, 1e-3, 1e-3, 1e-1, 1e-1, 1e-1, 1e-1, 1e-1, 1e-1, 1e-1, 1e-1, 1e-1, 1e-1, 1e-3, 1e-5, 1e-5, 1e-5]
            #variance = [1e-3, 1e+3, 1e+6, 1e+8, 1e+8]
            m.set_target_variance(variance)
            m.refill_samples()
            end_MC = t.time()
            result.mc_levels = m.levels
            result.process_data()
            mean = result.average
            #print("MEAN", mean)
            mo.mean = mean
            moments = result.level_moments()
            result.format_result()
            result.time = end_MC - start_MC

        mc_data = result.levels_data[0]
        print("MOMENTY", moments)

        average = 0
        maximum = 0
        for index, level_data in enumerate(result.levels_data):
            if index > 0:
                abs_hod = [abs(data) for data in level_data]
                average += np.mean(level_data)
                maximum += np.amax(abs_hod)

        mc_data = [data + average for data in result.levels_data[0]]
        bounds = sc.stats.mstats.mquantiles(mc_data, prob=[eps, 1 - eps])
        #@TODO change bounds, this bounds doesn't work for other simulations
        function.bounds = bounds
        function.fixed_quad_n = moments_number ** 2
        #function.mean = mean


        """
        for k in range(moments_number):
            val = []
            for value in mc_data:
                val.append(function.get_moments(value, k))
            new_moments.append(np.mean(val))


        print("momenty z distribuce ", new_moments)
        #print("momenty z hodnot ", real_moments)
        """

        """
        sigma = 0
        for index, moment in enumerate(moments):
            sigma += math.sqrt(np.var([moment, new_moments[index]]))
        print("sigma", sigma)
        """

        function.mean = mean

        # Run distribution
        distribution = Distribution(function, moments_number, moments, toleration)
        distribution.newton_method()

        # Empirical distribution function
        ecdf = ECDF(mc_data)
        samples = np.linspace(bounds[0], bounds[1], len(mc_data))
        distribution_function = []
        difference = 0
        KL_divergence = 0
        ## Set approximate density values
        approximate_density = []

        def integrand(x):
            return distribution.density(x)

        def kullback_leibler_distance(x, exact_value):
            print(x)
            print("distribution density", distribution.density(x))
            print("exact value", exact_value)

            distribution.density(x) * math.log(distribution.density(x) / exact_value)

        for step, value in enumerate(samples):
            integral = sc.integrate.quad(integrand, bounds[0], value)
            approximate_density.append(distribution.density(value))
            distribution_function.append(integral[0])
            difference += abs(ecdf.y[step] - integral[0])**2
            integ = sc.integrate.quad(kullback_leibler_distance, bounds[0], value, args=(ecdf.y[step]))
            KL_divergence += integ




        print("Aproximované momenty", distribution.approximation_moments)
        print("Původní momenty", moments)
        print("Kullback-Leibler distance", KL_divergence)

        plt.figure(1)
        plt.plot(ecdf.x, ecdf.y)
        plt.plot(samples, distribution_function, 'r')

        ## Show approximate and exact density

        plt.figure(2)
        plt.plot(samples, approximate_density, 'r')
        plt.plot(samples, [sc.stats.norm.pdf(sample, 2, 1) for sample in samples])

        plt.show()

        '''
        sum = 0
        stredni_hodnota = 50
        for i in range(1):
            sum = sum + pow((stredni_hodnota -Y[i]),2)
        chyba = np.sqrt(sum/10)
        end = t.time()

        print("Y = ", m.average(Y))
        print("Chyba = ", chyba)

        print("cas", end - start)
        '''

    if __name__ == "__main__":
        main()