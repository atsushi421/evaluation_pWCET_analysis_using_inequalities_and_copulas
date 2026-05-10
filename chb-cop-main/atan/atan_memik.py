import os
import math
import numpy as np
from sklearn.linear_model import LinearRegression
from concurrent.futures import ProcessPoolExecutor, as_completed


def estimate_kth_moment(inputa: np.ndarray, k: int, d: int) -> float:
    '''
    Estimate the k-th moment of the input array, E[arctan(X/d)^k].

    Args:
        inputa (np.ndarray): Input array.
        k (int): The moment to estimate.
        d (int): The divisor for the arctan function.
    Returns:
        float: The estimated k-th moment.
    '''
    return np.mean(np.arctan(np.asarray(inputa, dtype=np.float64) / d) ** k)


def estimate_log_kth_moment(inputa: np.ndarray, k: int, d: int) -> float:
    '''
    Estimate the log of the k-th moment of the input array using log-sum-exp trick.

    Args:
        inputa (np.ndarray): Input array.
        k (int): The moment to estimate.
        d (int): The divisor for the arctan function.
    Returns:
        float: The estimated log of the k-th moment.
    '''
    log_inputa = np.log(np.arctan(inputa / d))
    log_power = log_inputa * k
    max_log_power = np.max(log_power)
    log_sum_exp = np.log(
        np.sum(np.exp(log_power - max_log_power))) + max_log_power
    log_mean = log_sum_exp - np.log(len(inputa))

    return log_mean


def calc_quantile_pred(samples_boot: np.ndarray, p: float, k: int, d: int) -> float:
    '''
    Calculate the quantile prediction for the given samples.

    Args:
        samples_boot (np.ndarray): Bootstrapped samples.
        p (float): Probability.
        k (int): Moment order.
    Returns:
        float: The quantile prediction.
    '''
    moment = estimate_kth_moment(samples_boot, k, d)
    target_theta = (moment / p) ** (1/k)
    if target_theta >= np.pi/2:
        return np.inf
    else:
        return np.tan(target_theta) * d
    # return np.tan((estimate_kth_moment(samples_boot, k, d)/p) ** (1/k)) * d


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

    max_k_test.update({p: round(pred) for p, pred in zip(
        p_all, predicted_values) if p not in max_k_test})

    return max_k_test


def validate_corr(max_k: dict[float, int], corr_th: float):
    corr: float = np.corrcoef(
        np.log10(list(max_k.keys())), list(max_k.values()))[0, 1]
    print(f'Correlation coefficient: {corr}')
    if corr > corr_th:
        raise ValueError(
            f'Correlation coefficient {corr} exceeds threshold {corr_th}.')


def simulation_for_one_p(p, samples, n_boot, k_start, k_end, q_est, d):
    """
    1回のシミュレーションを実行して、与えられた d に対する current_k を返す。
    ここでは f(x) = (arctan(x/d))^k を使った moment に基づく分位数予測 calc_quantile_pred を利用する。

    Args:
        p (float): 対象の確率
        samples (np.ndarray): 入力サンプル
        n_boot (int): ブートストラップサンプル数
        k_start (int): k の開始値
        k_end (int): k の終了値
        q_est (float): サンプルからの経験的分位数（np.quantile(samples, 1 - p) など）
        d (int or float): arctan の引数に使う定数

    Returns:
        int or float: シミュレーション内で得られた current_k。更新がなければ inf を返す。
    """
    samples_boot = np.random.choice(samples, size=n_boot, replace=True)
    tightness_best = np.inf
    current_k = None
    for k in range(k_start, k_end + 1):
        # calc_quantile_pred は d をパラメータとして利用するようになっている
        vpred = calc_quantile_pred(samples_boot, p, k, d)
        tightness = vpred / q_est
        if tightness < 1:
            break
        if tightness < tightness_best:
            tightness_best = tightness
            current_k = k
    return current_k if current_k is not None else k_end


def restk(samples: np.ndarray, k_start: int, k_end: int, n_sims: int,
          p_test: list[float], p_all: list[float], d_list: list[int],
          corr_th: float, n_boot: int = None) -> dict[float, dict[float, int]]:
    """
    d_list に含まれる各 d について、シミュレーションにより各 p に対する最大 k を求める。

    Args:
        samples (np.ndarray): 入力サンプル
        k_start (int): k の開始値
        k_end (int): k の終了値
        n_sims (int): シミュレーションの反復回数
        p_test (list[float]): テストに用いる確率のリスト
        p_all (list[float]): 最終的に予測するすべての確率のリスト
        d_list (list[int]): d の値のリスト。各 d についてシミュレーションを行う。
        corr_th (float): 相関の閾値
        n_boot (int, optional): ブートストラップサンプル数。None の場合は samples の長さを使用。

    Returns:
        dict[float, dict[float, int]]: キーが d、値が各 p に対する max_k の辞書
    """
    if n_boot is None:
        n_boot = len(samples)

    result = {}  # 結果は {d: {p: max_k, ...}, ...} の形式で返す
    for d in d_list:
        max_k_test: dict[float, int] = {}
        for p in p_test:
            q_est: float = np.quantile(samples, 1 - p)
            simulation_results = []
            with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
                futures = [
                    executor.submit(simulation_for_one_p, p,
                                    samples, n_boot, k_start, k_end, q_est, d)
                    for _ in range(n_sims)
                ]
                for future in as_completed(futures):
                    simulation_results.append(future.result())
            max_k_test[p] = min(
                simulation_results) if simulation_results else None

        # p_test で得られた max_k_test に対して、線形回帰で p_all も予測する（predict_max_k_linear, validate_corr は既存関数）
        max_k_all: dict[float, int] = predict_max_k_linear(max_k_test, p_all)
        validate_corr(max_k_all, corr_th)
        result[d] = max_k_all
        print(f'd: {d}, max_k_all: {max_k_all}')
    return result


def memik(samples: np.ndarray, p_all: list[float], d_max_k: dict[int, dict[float, int]], k_step: int, d_list: list[int]) -> dict[float, int]:
    '''
    Get the minimum envelope for each markov's inequality with power-of-k

    Args:
        samples (np.ndarray): Input samples.
        p_all (list[float]): Target probabilities.
        d_max_k (dict[int, dict[float, int]]): Dictionary mapping probabilities to k values.
        k_step (int): Step size for k.
        d_list (list[int]): List of d values for the arctan function.
    Returns:
        dict[float, int]: Dictionary mapping probabilities to WCET values.
    '''

    # precalculate moments for all k and d
    d_k_moments: dict[int, dict[int, float]] = {}
    for d in d_list:
        max_k = d_max_k[d]
        d_k_moments[d] = {}
        for k in range(1, max(max_k.values()) + 1):
            d_k_moments[d][k] = estimate_kth_moment(samples, k, d)

    envelope: dict[float, tuple[float, int, int]] = {}
    for p in p_all:
        mik_best: float = math.inf
        best_d = None
        best_k = None
        for d in d_list:
            best_in_d: float = math.inf
            best_k_in_d = None
            for k in range(1, d_max_k[d][p] + 1, k_step):
                target_theta = (d_k_moments[d][k] / p) ** (1/k)
                if target_theta >= np.pi/2:
                    continue
                pred: float = d * np.tan(target_theta)
                if pred > best_in_d:
                    break
                else:
                    best_in_d = pred
                    best_k_in_d = k
            if best_in_d < mik_best:
                mik_best = best_in_d
                best_d = d
                best_k = best_k_in_d
        envelope[p] = (mik_best, best_d, best_k)

    return envelope
