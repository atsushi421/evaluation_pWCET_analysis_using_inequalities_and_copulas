import os
import math
import numpy as np
from sklearn.linear_model import LinearRegression

def estimate_kth_moment(inputa: np.ndarray, k: int) -> float:
    '''
    Estimate the k-th moment of the input array.

    Args:
        inputa (np.ndarray): Input array.
        k (int): The moment to estimate.
    Returns:
        float: The estimated k-th moment.
    '''
    return np.mean(np.asarray(inputa, dtype=np.float64) ** k)

def estimate_log_kth_moment(inputa: np.ndarray, k: int) -> float:
    '''
    Estimate the log of the k-th moment of the input array using log-sum-exp trick.

    Args:
        inputa (np.ndarray): Input array.
        k (int): The moment to estimate.
    Returns:
        float: The estimated log of the k-th moment.
    '''
    log_inputa = np.log(inputa)
    log_power = log_inputa * k
    max_log_power = np.max(log_power)
    log_sum_exp = np.log(np.sum(np.exp(log_power - max_log_power))) + max_log_power
    log_mean = log_sum_exp - np.log(len(inputa))

    return log_mean

def calc_quantile_pred(samples_boot: np.ndarray, p: float, k: int) -> float:
    '''
    Calculate the quantile prediction for the given samples.

    Args:
        samples_boot (np.ndarray): Bootstrapped samples.
        p (float): Probability.
        k (int): Moment order.
    Returns:
        float: The quantile prediction.
    '''
    log_moment = estimate_log_kth_moment(samples_boot, k)
    return np.exp((log_moment - np.log(p)) / k)

def predict_max_k_linear(max_k_test: dict[float, int], p_all: list[float]) -> dict[float, int]:
    '''
    Predict the maximum k for each probability using linear regression.

    Args:
        max_k_test (dict[float, int]): Dictionary mapping test probabilities to k values.
        p_all (list[float]): All target probabilities.
    Returns:
        dict[float, int]: Dictionary mapping all probabilities to predicted k values.
    '''
    model: LinearRegression = LinearRegression().fit(
        np.log10(np.array(list(max_k_test.keys()))).reshape(-1, 1),
        np.array(list(max_k_test.values()))
    )

    predicted_values: np.ndarray = model.predict(
        np.log10(np.array(p_all)).reshape(-1, 1)
    )

    max_k_test.update({p: round(pred) for p, pred in zip(p_all, predicted_values) if p not in max_k_test})

    return max_k_test

def validate_corr(max_k: dict[float, int], corr_th: float):
    corr: float = np.corrcoef(np.log10(list(max_k.keys())), list(max_k.values()))[0, 1]
    print(f'Correlation coefficient: {corr}')
    if corr > corr_th:
        raise ValueError(f'Correlation coefficient {corr} exceeds threshold {corr_th}.')

from concurrent.futures import ProcessPoolExecutor, as_completed

def simulation_for_one_p(p, samples, n_boot, k_start, k_end, q_est):
    samples_boot = np.random.choice(samples, size=n_boot, replace=True)
    tightness_best = math.inf
    current_k = None
    for k in range(k_start, k_end + 1):
        vpred = calc_quantile_pred(samples_boot, p, k)
        tightness = vpred / q_est
        if tightness < 1:
            break
        if tightness < tightness_best:
            tightness_best = tightness
            current_k = k
    return current_k if current_k is not None else float('inf')

def restk(samples: np.ndarray, k_start: int, k_end: int, n_sims: int,
                   p_test: list[float], p_all: list[float], corr_th: float, n_boot: int = None) -> dict[float, int]:
    """
    Find the upper bound of k for each target probability via parallel simulation.

    Args:
        samples (np.ndarray): Input samples.
        k_start (int): Start value for k.
        k_end (int): End value for k.
        n_sims (int): Number of simulations.
        p_test (list[float]): Test probabilities.
        p_all (list[float]): All target probabilities.
        corr_th (float): Correlation threshold.
        n_boot (int, optional): Number of bootstrap samples. Defaults to len(samples).
    Returns:
        dict[float, int]: Dictionary mapping probabilities to k values.
    """
    if n_boot is None:
        n_boot = len(samples)

    max_k_test: dict[float, int] = {}

    for p in p_test:
        q_est: float = np.quantile(samples, 1 - p)
        simulation_results = []
        with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
            futures = [
                executor.submit(simulation_for_one_p, p, samples, n_boot, k_start, k_end, q_est)
                for _ in range(n_sims)
            ]
            for future in as_completed(futures):
                result = future.result()
                simulation_results.append(result)
        max_k_test[p] = min(simulation_results) if simulation_results else None

    max_k_all: dict[float, int] = predict_max_k_linear(max_k_test, p_all)
    validate_corr(max_k_all, corr_th)
    return max_k_all

# def restk(samples: np.ndarray, k_start: int, k_end: int, n_sims: int, p_test: list[float], p_all: list[float], corr_th: float, n_boot: int = None) -> dict[float, int]:
#     '''
#     Restrict k for each target probability.

#     Args:
#         samples (np.ndarray): Input samples.
#         k_start (int): Start value for k.
#         k_end (int): End value for k.
#         n_boot (int, optional): Number of bootstrap samples. Defaults to None.
#         n_sims (int): Number of simulations.
#         p_test (list[float]): Test probabilities.
#         p_all (list[float]): All probabilities.
#         corr_th (float): Correlation threshold.
#     Returns:
#         dict[float, int]: Dictionary mapping probabilities to k values.
#     '''

#     if n_boot is None:
#         n_boot = len(samples)

#     # Initialize the result dictionary
#     max_k_test: dict[float, int] = {}
#     tightness_best: dict[float, float] = {}

#     for p in p_test:
#         q_est: float = np.quantile(samples, 1-p)
#         current_k: int = 1
#         for _ in range(n_sims):
#             samples_boot: np.ndarray = np.random.choice(samples, size=n_boot, replace=True)
#             tightness_best[p] = math.inf
#             for k in range(k_start, k_end+1, 1):
#                 vpred: float = calc_quantile_pred(samples_boot, p, k)
#                 tightness: float = vpred/q_est
#                 if tightness < 1:
#                     break
#                 if tightness < tightness_best[p]:
#                     tightness_best[p] = tightness
#                     current_k = k
#             if current_k < max_k_test.get(p, math.inf):
#                 max_k_test[p] = current_k

#     max_k_all: dict[float, int] = predict_max_k_linear(max_k_test, p_all)

#     validate_corr(max_k_all, corr_th)

#     return max_k_all

def memik(samples: np.ndarray, p_all: list[float], max_k: dict[float, int], k_step: int) -> dict[float, int]:
    '''
    Get the minimum envelope for each markov's inequality with power-of-k

    Args:
        samples (np.ndarray): Input samples.
        p_all (list[float]): Target probabilities.
        max_k (dict[float, int]): Dictionary mapping probabilities to k values.
        k_step (int): Step size for k.
    Returns:
        dict[float, int]: Dictionary mapping probabilities to WCET values.
    '''

    # precalculate log of moments for all k
    log_kth_moments: dict[int, float] = {}
    for k in range(1, max(max_k.values()) + 1):
        log_kth_moments[k] = estimate_log_kth_moment(samples, k)

    # calculate the minimum envelope for each probability
    envelope: dict[float, int] = {}
    for p in p_all:
        mik_best: float = math.inf
        best_k = None
        for k in range(1, max_k[p] + 1, k_step):
            pred: float = math.exp((1/k) * (log_kth_moments[k] - np.log(p)))
            if pred > mik_best:
                break
            else:
                mik_best = pred
                best_k = k
        envelope[p] = (mik_best, best_k)

    return envelope
