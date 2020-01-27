import os
import sys
import shutil
from scipy import stats

src_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(src_path, '..', 'src/mlmc'))
from synth_simulation import SynthSimulation
from sampler import Sampler
from sample_storage import Memory
from sampling_pool import ProcessPool, ThreadPool, OneProcessPool
from mlmc.moments import Legendre


def one_process_sampler_test():
    """
    Test sampler, simulations are running in same process, artificial simulation is used
    :return:
    """
    n_moments = 5
    failed_fraction = 0.0

    distr = stats.norm()

    step_range = [0.1, 0.006]

    # Create simulation instance
    simulation_config = dict(distr=distr, complexity=2, nan_fraction=failed_fraction, sim_method='_sample_fn')
    simulation_factory = SynthSimulation(simulation_config)

    sample_storage = Memory()
    sampling_pool = OneProcessPool()

    # Plan and compute samples
    sampler = Sampler(sample_storage=sample_storage, sampling_pool=sampling_pool, sim_factory=simulation_factory,
                      step_range=step_range)

    true_domain = distr.ppf([0.0001, 0.9999])
    moments_fn = Legendre(n_moments, true_domain)

    sampler.set_initial_n_samples()
    sampler.schedule_samples()
    sampler.ask_sampling_pool_for_samples()

    sampler.target_var_adding_samples(1e-4, moments_fn)
    sampler.schedule_samples()
    sampler.ask_sampling_pool_for_samples()

    storage = sampler.sample_storage
    results = storage.sample_pairs()
    print("results ", results)


if __name__ == "__main__":
    one_process_sampler_test()