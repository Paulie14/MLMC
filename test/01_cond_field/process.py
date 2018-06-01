import os
import sys
import json
import shutil
import copy
#import statprof
import numpy as np
import scipy.stats as stats
import scipy.integrate as integrate

src_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append( os.path.join(src_path, '..', '..', 'src'))

import mlmc.mlmc
import mlmc.simulation
import mlmc.moments
import mlmc.distribution
import flow_pbs
import flow_mc as flow_mc



class ProcessMLMC:
    
    def __init__(self, work_dir):        
        self.work_dir = os.path.abspath(work_dir)
        self._serialize = ['work_dir', 'output_dir', 'n_levels', 'step_range']

    def get_root_dir(self):
        root_dir = os.path.abspath(self.work_dir)
        while root_dir != '/':
            root_dir, tail = os.path.split(root_dir)
        return tail

    def setup_environment(self):
        self.pbs_config = dict(
            package_weight=250000,  # max number of elements per package
            n_cores=1,
            n_nodes=1,
            select_flags=['cgroups=cpuacct'],
            mem='4gb',
            queue='charon')

        print("root: '", self.get_root_dir(),"'")
        if self.get_root_dir() == 'storage':
            # Metacentrum
            self.sample_sleep = 30
            self.init_sample_timeout = 600
            self.sample_timeout = 0
            self.pbs_config['qsub'] = '/usr/bin/qsub'
            flow123d = "/storage/praha1/home/jan_brezina/local/flow123d_2.2.0/flow123d"
            gmsh = "/storage/liberec1-tul/home/martin_spetlik/astra/gmsh/bin/gmsh"
        else:
            # Local
            self.sample_sleep = 1
            self.init_sample_timeout = 60
            self.pbs_config['qsub'] = os.path.join(src_path, '..', 'mocks', 'qsub')
            #flow123d = "/home/jb/workspace/flow123d/bin/fterm flow123d dbg"
            flow123d = os.path.join(src_path, '..', 'mocks', 'flow_mock')
            gmsh = "/home/jb/local/gmsh-3.0.5-git-Linux/bin/gmsh"

        self.env = dict(
            flow123d=flow123d,
            gmsh=gmsh,
        )

    def _set_n_levels(self, nl):
        self.n_levels = nl
        self.output_dir = os.path.join(self.work_dir, "output_{}".format(nl))
        self._setup_file = os.path.join(self.output_dir, "setup.json")

    def setup(self, n_levels):
        self._set_n_levels(n_levels)
        self.output_dir = os.path.join(self.work_dir, "output_{}".format(n_levels))

        self.setup_environment()

        self.fields_config = dict(
            conductivity=dict(
                corr_exp='gauss',
                dim=2,
                corr_length=0.5,
                log=True
            ))

        self.step_range = (1, 0.01)
        yaml_path = os.path.join(self.work_dir, '01_conductivity.yaml')
        geo_path = os.path.join(self.work_dir, 'square_1x1.geo')
        self.simulation_config = {
            'env': self.env,  # The Environment.
            'output_dir': self.output_dir,
            'field_name': self.fields_config,  # correlated_field.FieldSet object
            'yaml_file': yaml_path,  # The template with a mesh and field placeholders
            'sim_param_range': self.step_range,  # Range of MLMC simulation parametr. Here the mesh step.
            'geo_file': geo_path,  # The file with simulation geometry (independent of the step)
            #'field_template': "!FieldElementwise {mesh_data_file: \"${INPUT}/%s\", field_name: %s}"
            'field_template': "!FieldElementwise {gmsh_file: \"${INPUT}/%s\", field_name: %s}"
        }

    @staticmethod
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    def initialize(self, clean):
        print('init')
        self.pbs_work_dir = os.path.join(self.output_dir, "scripts")
        self.pbs = flow_pbs.FlowPbs(self.pbs_work_dir,
                       qsub=self.pbs_config['qsub'],
                       clean=clean)
        self.pbs.pbs_common_setting(**self.pbs_config)
        if not clean:
            print('read logs')
            self.pbs.reload_logs()
            print('done')
        self.env['pbs'] = self.pbs

        flow_mc.FlowSim.total_sim_id = 0
        self.simultion_factory = flow_mc.FlowSim.factory(self.step_range,
            config = self.simulation_config, clean=clean)

        self.mc = mlmc.mlmc.MLMC(self.n_levels, self.simultion_factory, self.pbs)
        if clean:
            assert ProcessMLMC.is_exe(self.env['flow123d'])
            assert ProcessMLMC.is_exe(self.env['gmsh'])
            assert ProcessMLMC.is_exe(self.pbs_config['qsub'])
            self.save()

    def collect(self):
        return self.mc.wait_for_simulations(sleep=self.sample_sleep, timeout=0.1)

    def set_moments(self, n_moments, log=False):
        self.moments_fn = mlmc.moments.LegendreMoments(n_moments, self.domain, safe_eval=True, log=log)
        return self.moments_fn

    def n_sample_estimate(self, target_variance):
        self.n_samples = self.mc.set_initial_n_samples([30, 3])
        self.mc.refill_samples()
        self.mc.wait_for_simulations(sleep=self.sample_sleep, timeout=self.init_sample_timeout)

        self.domain = self.mc.estimate_domain()
        self.mc.set_target_variance(0.001, self.moments_fn, 2.0)

    def generate_jobs(self, n_samples=None, target_variance = None):
        if n_samples is not None:
            self.mc.set_initial_n_samples(n_samples)
        self.mc.refill_samples()
        self.mc.wait_for_simulations(sleep=self.sample_sleep, timeout=self.sample_timeout)


    def save(self):

        setup={}
        for key in self._serialize:
            setup[key] = self.__dict__.get(key, None)
        with open(self._setup_file, 'w') as f:
            json.dump(setup, f)

      
    def load(self, n_levels):
        
        self._set_n_levels(n_levels)
        self.setup(n_levels)
        print('read  setup')
        # read setup
        with open(self._setup_file, 'r') as f:
            setup = json.load(f)
        for key in self._serialize:
            self.__dict__[key] = setup.get(key, None)
        
        self.initialize(clean=False)
        
        
    #     self.distr = distr
    #     self.n_levels = n_levels
    #     self.n_moments = n_moments
    #
    #     # print("var: ", distr.var())
    #     step_range = (0.8, 0.01)
    #     coef = (step_range[1]/step_range[0])**(1.0/(self.n_levels - 1))
    #     self.steps = step_range[0] * coef**np.arange(self.n_levels)
    #     self.mc, self.sims = self.make_simulation_mc(step_range)
    #
    #     # reference variance
    #     true_domain = distr.ppf([0.001, 0.999])
    #     self.moments_fn = lambda x, n=n_moments, a=true_domain[0], b=true_domain[1]: \
    #                                 mlmc.moments.legendre_moments(x, n, a, b)
    #
    #     sample_size = 10000
    #     self.exact_mean = self.mc_estimate_exact_mean(self.moments_fn, 5*sample_size)
    #     means, vars = self.mc_estimate_diff_var(self.moments_fn, sample_size)
    #     self.ref_diff_vars = np.array(vars)[:, :]
    #     self.ref_vars = np.sum(np.array(vars)/sample_size, axis=0)
    #     self.ref_means = np.sum(np.array(means), axis=0)
    #     #print("Ref means: ", ref_means)
    #     #print("Ref vars: ", ref_vars)
    #
    # def make_simulation_mc(self, step_range):
    #
    # def direct_estimate_diff_var(self, moments_fn, domain):
    #     means = []
    #     vars = []
    #     sim_l = None
    #     for l in range(len(self.sims)):
    #         sim_0 = sim_l
    #         sim_l = lambda x, h=self.sims[l].step: self.sims[l]._sample_fn(x, h)
    #         if l == 0:
    #             md_fn = lambda x: moments_fn(sim_l(x))
    #         else:
    #             md_fn = lambda x: moments_fn(sim_l(x)) - moments_fn(sim_0(x))
    #         fn = lambda x: (md_fn(x)).T * self.distr.pdf(x)
    #         moment_means = integrate.fixed_quad(fn, domain[0], domain[1], n=100)[0]
    #         fn2 = lambda x: ((md_fn(x) - moment_means[None, :]) ** 2).T * self.distr.pdf(x)
    #         moment_vars = integrate.fixed_quad(fn2, domain[0], domain[1], n=100)[0]
    #         means.append(moment_means)
    #         vars.append(moment_vars)
    #     return means, vars
    #
    # def mc_estimate_diff_var(self, moments_fn, size=10000):
    #     """
    #     :param moments_fn:
    #     :param domain:
    #     :param distr:
    #     :param sims:
    #     :return: means, vars ; shape n_levels, n_moments
    #     """
    #     means = []
    #     vars = []
    #     sim_l = None
    #     for l in range(len(self.sims)):
    #         sim_0 = sim_l
    #         sim_l = lambda x, h=self.sims[l].step: self.sims[l]._sample_fn(x, h)
    #         X = self.distr.rvs(size=size)
    #         if l == 0:
    #             MD = moments_fn(sim_l(X))
    #         else:
    #             MD = (moments_fn(sim_l(X)) - moments_fn(sim_0(X)))
    #
    #         moment_means = np.mean(MD, axis=0)
    #         moment_vars = np.var(MD, axis=0, ddof=1)
    #         means.append(moment_means)
    #         vars.append(moment_vars)
    #     return np.array(means), np.array(vars)
    #
    # def mc_estimate_exact_mean(self, moments_fn, size= 20000):
    #     X = self.distr.rvs(size=size)
    #     return np.mean(moments_fn(X), axis=0)
    #
    #
    # def generate_samples(self, size):
    #     # generate samples
    #     self.mc.set_initial_n_samples(self.n_levels*[size])
    #     self.mc.refill_samples()
    #     self.mc.wait_for_simulations()
    #
    # # @staticmethod
    # # def box_plot(ax, X, Y):
    # #     bp = boxplot(column='age', by='pclass', grid=False)
    # #     for i in [1, 2, 3]:
    # #         y = titanic.age[titanic.pclass == i].dropna()
    # #         # Add some random "jitter" to the x-axis
    # #         x = np.random.normal(i, 0.04, size=len(y))
    # #         plot(x, y, 'r.', alpha=0.2)
    #
    # def plot_mlmc_conv(self, target_var):
    #     import matplotlib.pyplot as plt
    #
    #     fig = plt.figure(figsize=(10,20))
    #
    #     for m in range(1, self.n_moments):
    #         ax = fig.add_subplot(2, 2, m)
    #         color = 'C' + str(m)
    #         Y = np.var(self.means_est[:,:,m], axis=1)
    #         ax.plot(target_var, Y, 'o', c=color, label=str(m))
    #
    #
    #         Y = np.percentile(self.vars_est[:, :, m],  [10, 50, 90], axis=1)
    #         ax.plot(target_var, Y[1,:], c=color)
    #         ax.plot(target_var, Y[0,:], c=color, ls='--')
    #         ax.plot(target_var, Y[2, :], c=color, ls ='--')
    #         Y = (self.exact_mean[m] - self.means_est[:, :, m])**2
    #         Y = np.percentile(Y, [10, 50, 90], axis=1)
    #         ax.plot(target_var, Y[1,:], c='gray')
    #         ax.plot(target_var, Y[0,:], c='gray', ls='--')
    #         ax.plot(target_var, Y[2, :], c='gray', ls ='--')
    #         ax.set_yscale('log')
    #         ax.set_xscale('log')
    #         ax.legend()
    #         ax.set_ylabel("observed var. of mean est.")
    #
    #     plt.show()
    #
    #
    #
    #
    #
    #
    #
    # def check_lindep(self, x, y, slope):
    #     fit = np.polyfit(np.log(x), np.log(y), deg=1)
    #     print("MC fit: ", fit, slope)
    #     assert np.isclose(fit[0], slope, rtol=0.2), (fit, slope)
    #
    # def convergence_test(self):
    #
    #
    #     # subsamples
    #     var_exp = np.linspace(-1, -4, 10)
    #     target_var = 10**var_exp
    #     means_el = []
    #     vars_el = []
    #     n_loops = 30
    #     for t_var in target_var:
    #         n_samples = self.mc.set_target_variance(t_var, prescribe_vars=self.ref_diff_vars)
    #         n_samples = np.max(n_samples, axis=1).astype(int)
    #
    #         print( t_var, n_samples)
    #         n_samples = np.minimum(n_samples, (self.mc.n_samples*0.9).astype(int))
    #         n_samples = np.maximum(n_samples, 1)
    #         for i in range(n_loops):
    #             self.mc.subsample(n_samples)
    #             means_est, vars_est = self.mc.estimate_moments(self.moments_fn)
    #             means_el.append(means_est)
    #             vars_el.append(vars_est)
    #     self.means_est = np.array(means_el).reshape(len(target_var), n_loops, self.n_moments)
    #     self.vars_est = np.array(vars_el).reshape(len(target_var), n_loops, self.n_moments)
    #
    #     #self.plot_mlmc_conv(target_var)
    #
    #     for m in range(1, self.n_moments):
    #         Y = np.var(self.means_est[:,:,m], axis=1)
    #         self.check_lindep(target_var, Y, 1.0)
    #         Y = np.mean(self.vars_est[:, :, m], axis=1)
    #         self.check_lindep(target_var, Y , 1.0)
    #
    #         X = np.tile(target_var, n_loops)
    #         Y = np.mean(np.abs(self.exact_mean[m] - self.means_est[:, :, m])**2, axis=1)
    #         self.check_lindep(target_var, Y,  1.0)
    #
    def plot_diff_var(self):
        import matplotlib.pyplot as plt
        fig = plt.figure(figsize=(10,20))
        ax = fig.add_subplot(1, 1, 1)

        error_power = 2.0
        for m in range(1, self.n_moments):
            color = 'C' + str(m)
            Y = self.ref_diff_vars[:,m]/(self.steps**error_power)

            ax.plot(self.steps[1:], Y[1:], c=color, label=str(m))
            ax.plot(self.steps[0], Y[0], 'o', c=color)
        #
        #
        #     Y = np.percentile(self.vars_est[:, :, m],  [10, 50, 90], axis=1)
        #     ax.plot(target_var, Y[1,:], c=color)
        #     ax.plot(target_var, Y[0,:], c=color, ls='--')
        #     ax.plot(target_var, Y[2, :], c=color, ls ='--')
        #     Y = (self.exact_mean[m] - self.means_est[:, :, m])**2
        #     Y = np.percentile(Y, [10, 50, 90], axis=1)
        #     ax.plot(target_var, Y[1,:], c='gray')
        #     ax.plot(target_var, Y[0,:], c='gray', ls='--')
        #     ax.plot(target_var, Y[2, :], c='gray', ls ='--')
        ax.set_yscale('log')
        ax.set_xscale('log')
        ax.legend()
        ax.set_ylabel("observed var. of mean est.")

        plt.show()

    def plot_n_sample_est_distributions(self, cost, total_std, n_samples):
        import matplotlib.pyplot as plt

        fig = plt.figure(figsize=(30,10))
        ax1 = fig.add_subplot(1, 3, 1)
        ax1.hist(cost, normed=1)
        ax1.set_xlabel("cost")
        cost_99 = np.percentile(cost, [99])
        ax1.axvline(x=cost_99, label=str(cost_99), c='red')
        ax1.legend()

        ax2 = fig.add_subplot(1, 3, 2)
        ax2.hist(total_std, normed=1)
        ax2.set_xlabel("total var")
        tstd_99 = np.percentile(total_std, [99])
        ax2.axvline(x=tstd_99, label=str(tstd_99), c='red')
        ax2.legend()

        ax3 = fig.add_subplot(1, 3, 3)
        ax3.hist(n_samples, normed=1)
        ax3.set_xlabel("n_samples")
        ns_99 = np.percentile(n_samples, [99])
        ax3.axvline(x=ns_99, label=str(ns_99), c='red')
        ax3.legend()

        plt.show()

    def test_min_samples(self):
        """
        How many samples we need on every level to get same Nl or higher but
        with at most 10% cost increase in 99%
        :return:
        """


        t_var = 0.0002
        ref_n_samples = self.mc.set_target_variance(t_var, prescribe_vars=self.ref_diff_vars)
        ref_n_samples = np.max(ref_n_samples, axis=1)
        ref_cost = self.mc.estimate_cost(n_samples=ref_n_samples.astype(int))
        ref_total_var = np.sum(self.ref_diff_vars / ref_n_samples[:, None])/self.n_moments
        n_samples = self.n_levels*[100]
        n_loops = 10

        print("ref var: {} target var: {}".format(ref_total_var, t_var))
        print(ref_n_samples.astype(int))

        # subsamples
        l_cost_err = []
        l_total_std_err = []
        l_n_samples_err = []
        for i in range(n_loops):
            fractions = [0, 0.001, 0.01, 0.1,  1]
            for fr in fractions:
                if fr == 0:
                    nL, n0 = 3, 30
                    L = max(2, self.n_levels)
                    factor = (nL / n0) ** (1 / (L - 1))
                    n_samples = (n0 * factor ** np.arange(L)).astype(int)
                else:
                    n_samples = np.maximum( n_samples, (fr*max_est_n_samples).astype(int))
                # n_samples = np.maximum(n_samples, 1)

                self.mc.subsample(n_samples)
                est_diff_vars, _ = self.mc.estimate_diff_vars(self.moments_fn)
                est_n_samples = self.mc.set_target_variance(t_var, prescribe_vars=est_diff_vars)
                max_est_n_samples = np.max(est_n_samples, axis=1)
                est_cost = self.mc.estimate_cost(n_samples=max_est_n_samples.astype(int))
                est_total_var = np.sum(self.ref_diff_vars / max_est_n_samples[:, None])/self.n_moments

                n_samples_err = np.min( (max_est_n_samples - ref_n_samples) /ref_n_samples)
                #total_std_err =  np.log2(est_total_var/ref_total_var)/2
                total_std_err = (np.sqrt(est_total_var) - np.sqrt(ref_total_var)) / np.sqrt(ref_total_var)
                cost_err = (est_cost - ref_cost)/ref_cost
                print("Fr: {:6f} NSerr: {} Tstderr: {} cost_err: {}".format(fr, n_samples_err, total_std_err, cost_err))
            print("est cost: {} ref cost: {}".format(est_cost, ref_cost))
            print(n_samples)
            print(np.maximum( n_samples, (max_est_n_samples).astype(int)))
            print(ref_n_samples.astype(int))
            print("\n")
            #l_n_samples_err.append(n_samples_err)
            #l_total_std_err.append( )
            #l_cost_err.append((ref_cost - est_cost)/ref_cost)

        # l_cost_err.sort()
        # l_total_std_err.sort()
        # l_n_samples_err.sort()
        # self.plot_n_sample_est_distributions(l_cost_err, l_total_std_err, l_n_samples_err)



    @staticmethod
    def ecdf(x):
        xs = np.sort(x)
        ys = np.arange(1, len(xs)+1)/float(len(xs))
        return xs, ys

    def plot_pdf_approx(self, ax1, ax2, mc0_samples):
        import matplotlib.pyplot as plt
        
        X = np.exp( np.linspace(np.log(self.domain[0]), np.log(self.domain[1]), 1000) )
        bins = np.exp( np.linspace(np.log(self.domain[0]), np.log(10), 60) )
        
        n_levels = self.mc.n_levels
        color = "C{}".format(n_levels)
        label = "l {}".format(n_levels)
        Y = self.distr_obj.density(X)
        ax1.plot(X, Y, c=color, label=label)
        
        Y = self.distr_obj.cdf(X)
        ax2.plot(X, Y, c=color, label=label)
        
        if n_levels == 1:
            ax1.hist(mc0_samples, normed=1,  bins=bins, alpha = 0.3, label='full MC', color=color)
            X, Y = ProcessMLMC.ecdf(mc0_samples)
            ax2.plot(X, Y, 'red')

            #Y = stats.lognorm.pdf(X, s=1, scale=np.exp(0.0))
            #ax1.plot(X, Y, c='gray', label="stdlognorm")
            #Y = stats.lognorm.cdf(X, s=1, scale=np.exp(0.0))
            #ax2.plot(X, Y, c='gray')
          
        ax1.axvline(x=self.est_domain[0], c=color)
        ax1.axvline(x=self.est_domain[1], c=color)
          
        
        

    @staticmethod    
    def align_array(arr):
        return "[" + ", ".join([ "{:10.5f}".format(x) for x in arr]) + "]" 
  


    def compute_results(self, mlmc_0, n_moments):
        self.domain = mlmc_0.ref_domain         
        self.est_domain = self.mc.estimate_domain()
        
        moments_fn = self.set_moments(n_moments, log=True)       
        self.est_moments, self.est_vars = self.mc.estimate_moments(moments_fn)
        self.est_std = np.sqrt(self.est_vars)
        
              
        #a, b = self.domain              
        #distr_mean = self.distr_mean = moments_fn.inv_linear(ref_means[1])
        #distr_var  = ((2*ref_means[2] + 1)/3 - ref_means[1]**2) / 4 * ((b-a)**2)        
        #self.distr_std  = np.sqrt(distr_var)

        
        moments_data = np.stack( (self.est_moments, self.est_vars), axis=1)    
        self.distr_obj = mlmc.distribution.Distribution(moments_fn, moments_data)
        self.distr_obj.domain = self.domain
        result = self.distr_obj.estimate_density(tol=0.01)
        #print(result)

        t_var = 1e-5
        diff_vars, _ = self.mc.estimate_diff_vars(moments_fn)
        diff_vars_max = np.max(diff_vars, axis =1)
        est_n_samples = self.mc.set_target_variance(t_var, prescribe_vars=diff_vars)
        self.est_n_samples = np.max(est_n_samples, axis=1)
        self.est_cost = self.mc.estimate_cost(n_samples = self.est_n_samples)
        
        print("\nLevels : ", self.mc.n_levels)
        #np.set_printoptions(precision=4, suppress=True, linewidth=140)
        print("moments:  ", self.align_array(self.est_moments))
        print("std:      ", self.align_array(self.est_std ))
        print("err:      ", self.align_array(self.est_moments - mlmc_0.est_moments ))
        print("domain:   ", self.est_domain)
        print("cost:     ", self.est_cost)
        print("dif_vars: ", self.align_array(diff_vars_max)) 
        print("ns :      ", self.align_array(self.est_n_samples))
        





def all_results(mlmc_list):
        import matplotlib.pyplot as plt

        fig = plt.figure(figsize=(30,10))
        ax1 = fig.add_subplot(1, 2, 1)
        ax2 = fig.add_subplot(1, 2, 2)
        #ax1.set_xscale('log')
        ax1.set_xlim(0.02, 10)
        ax2.set_xscale('log')
        
        n_moments = 5
        mc0_samples = mlmc_list[0].mc.levels[0].sample_values[:, 0]
        mlmc_list[0].ref_domain = (np.min(mc0_samples), np.max(mc0_samples) )         
        
        for prmc in mlmc_list:
            prmc.compute_results(mlmc_list[0], n_moments)
            prmc.plot_pdf_approx(ax1, ax2, mc0_samples)
        ax1.legend()
        ax2.legend()
        plt.show()



def all_collect(mlmc_list):
    running = 1
    while running > 0:
        running = 0
        for mc in mlmc_list:
            running += mc.collect()
        print("N running: ", running)    


def main():
    level_list = [9]
    
    print('main')
    command = sys.argv[1]
    work_dir = os.path.abspath(sys.argv[2])
    if command == 'run':
        os.makedirs(work_dir, mode=0o775, exist_ok=True)

        # copy
        for file_res in os.scandir(src_path):
            if (os.path.isfile(file_res.path)):
                shutil.copy(file_res.path, work_dir)
        
        mlmc_list = []
        for nl in [5,7]:
            mlmc = ProcessMLMC(work_dir)
            mlmc.setup(nl)
            mlmc.initialize(clean=True)
            mlmc.generate_jobs(n_samples=[10000, 100])
            mlmc_list.append(mlmc)  

        for nl in [3,4]:
            mlmc = ProcessMLMC(work_dir)
            mlmc.load(nl)
            mlmc_list.append(mlmc)  
            
        all_collect(mlmc_list)
        
    elif command == 'collect':
        assert os.path.isdir(work_dir)
        mlmc_list = []
        for nl in [ 5,7]:
            mlmc = ProcessMLMC(work_dir)
            mlmc.load(nl)
            mlmc_list.append(mlmc)  
        all_collect(mlmc_list)    
    
    elif command == 'process':
        assert os.path.isdir(work_dir)
        mlmc_list = []
        for nl in [ 1, 2,3 ,4,5,7,9]:
            prmc = ProcessMLMC(work_dir)
            prmc.load(nl)
            mlmc_list.append(prmc)  

        all_results(mlmc_list)
            
        

main()