"""
Модуль нагрузочного тестирования и обнаружения аномалий (SVD)
Социально-ориентированная веб-система

Содержит:
  LoadTester     — эмуляция нагрузочных испытаний
  AnomalyDetector — SVD-обнаружение аномалий активности пользователей
"""

import math
import random
import time
import logging
from typing import List, Dict, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ─── Обнаружение аномалий (SVD) ──────────────────────────────────────────────
class AnomalyDetector:
    """
    Обнаружение аномальной активности пользователей методом SVD.
    Алгоритм:
      1. Нормализация матрицы признаков X
      2. Вычисление доминирующего левого сингулярного вектора (power iteration)
      3. Реконструкция X_r из первой компоненты
      4. Ошибка реконструкции ||X_i - X_r_i|| > threshold → аномалия
    """

    def __init__(self, threshold_percentile: float = 95.0):
        self.threshold_percentile = threshold_percentile
        self.threshold_: float = 0.0
        self.singular_vector_: List[float] = []
        self.mean_: List[float] = []
        self.std_: List[float] = []

    # ── Нормализация ─────────────────────────────────────────────────────────
    @staticmethod
    def _normalize(X: List[List[float]]) -> Tuple[List[List[float]], List[float], List[float]]:
        n, m = len(X), len(X[0])
        means = [sum(X[i][j] for i in range(n)) / n for j in range(m)]
        stds = []
        for j in range(m):
            var = sum((X[i][j] - means[j]) ** 2 for i in range(n)) / n
            stds.append(math.sqrt(var) or 1.0)
        X_norm = [[(X[i][j] - means[j]) / stds[j] for j in range(m)] for i in range(n)]
        return X_norm, means, stds

    # ── Power Iteration для первого левого сингулярного вектора ─────────────
    @staticmethod
    def _power_iteration(X: List[List[float]], n_iter: int = 30) -> List[float]:
        n, m = len(X), len(X[0])
        rng = random.Random(0)
        v = [rng.gauss(0, 1) for _ in range(m)]
        # Нормировка
        norm_v = math.sqrt(sum(x ** 2 for x in v))
        v = [x / norm_v for x in v]

        for _ in range(n_iter):
            # u = X @ v
            u = [sum(X[i][j] * v[j] for j in range(m)) for i in range(n)]
            # sigma * u = ||u||
            sigma = math.sqrt(sum(x ** 2 for x in u))
            u = [x / sigma for x in u]
            # v = X^T @ u
            v = [sum(X[i][j] * u[i] for i in range(n)) for j in range(m)]
            norm_v = math.sqrt(sum(x ** 2 for x in v))
            v = [x / norm_v for x in v]
        return v

    def fit(self, X: List[List[float]]):
        X_norm, self.mean_, self.std_ = self._normalize(X)
        self.singular_vector_ = self._power_iteration(X_norm)

        # Реконструкция через первую компоненту
        errors = self._reconstruction_errors(X_norm)

        # Пороговое значение по перцентилю
        sorted_errs = sorted(errors)
        idx = int(len(sorted_errs) * self.threshold_percentile / 100)
        self.threshold_ = sorted_errs[min(idx, len(sorted_errs) - 1)]
        logger.info(f"AnomalyDetector fitted: threshold={self.threshold_:.4f}, "
                    f"n_samples={len(X)}")
        return self

    def _reconstruction_errors(self, X_norm: List[List[float]]) -> List[float]:
        v = self.singular_vector_
        n, m = len(X_norm), len(X_norm[0])
        errors = []
        for i in range(n):
            # Проекция на первую компоненту
            proj = sum(X_norm[i][j] * v[j] for j in range(m))
            x_rec = [proj * v[j] for j in range(m)]
            err = math.sqrt(sum((X_norm[i][j] - x_rec[j]) ** 2 for j in range(m)))
            errors.append(err)
        return errors

    def predict(self, X: List[List[float]]) -> List[bool]:
        """Возвращает True для аномальных наблюдений."""
        X_norm = [[(X[i][j] - self.mean_[j]) / self.std_[j]
                   for j in range(len(X[0]))] for i in range(len(X))]
        errors = self._reconstruction_errors(X_norm)
        return [e > self.threshold_ for e in errors], errors

    def detect_anomalous_users(self, user_activity: Dict[str, Dict[str, float]]) -> List[str]:
        """
        user_activity: {user_id: {feature: value, ...}}
        features: posts_per_day, likes_per_day, watch_time, reports_received
        """
        users = list(user_activity.keys())
        features = ["posts_per_day", "likes_per_day", "watch_time", "reports_received"]
        X = [[user_activity[u].get(f, 0.0) for f in features] for u in users]

        self.fit(X)
        anomalies, errors = self.predict(X)

        anomalous = [users[i] for i, is_anom in enumerate(anomalies) if is_anom]
        logger.info(f"Detected {len(anomalous)}/{len(users)} anomalous users")
        return anomalous, dict(zip(users, errors))


# ─── Эмулятор нагрузочного тестирования ──────────────────────────────────────
@dataclass
class RequestResult:
    rps: int
    mean_ms: float
    p95_ms: float
    error_rate: float
    cpu_pct: float
    throughput: float


class LoadTester:
    """
    Эмулятор нагрузочного тестирования системы.
    Моделирует реалистичные характеристики производительности
    с учётом деградации при росте нагрузки.
    """

    # Параметры модели производительности (microservices)
    BASE_MS = 55          # базовое время обработки запроса (мс)
    SATURATION_RPS = 900  # RPS насыщения
    MAX_CPU = 100.0

    def _response_time(self, rps: int, rng: random.Random) -> List[float]:
        """Генерация реалистичных времён отклика для набора запросов."""
        n = max(50, rps // 2)
        load_factor = (rps / self.SATURATION_RPS) ** 1.7
        mean = self.BASE_MS * (1 + 2.8 * load_factor)
        std = mean * (0.15 + 0.25 * load_factor)
        times = [max(10.0, rng.gauss(mean, std)) for _ in range(n)]
        # Редкие медленные запросы
        if rps > 400:
            n_slow = max(1, int(n * 0.05 * load_factor))
            for _ in range(n_slow):
                times.append(rng.gauss(mean * 3, mean))
        return times

    def _error_rate(self, rps: int) -> float:
        if rps < 300:
            return 0.0
        if rps < 600:
            return max(0.0, (rps - 300) / 30000)
        return min(0.15, 0.01 + ((rps - 600) / 900) ** 2.2 * 0.12)

    def _cpu(self, rps: int) -> float:
        return min(99.0, 10 + (rps / 1600) ** 0.9 * 88)

    def run(self, rps_levels: List[int], seed: int = 42) -> List[RequestResult]:
        rng = random.Random(seed)
        results = []
        logger.info("Запуск нагрузочного тестирования...")
        for rps in rps_levels:
            times = self._response_time(rps, rng)
            times_sorted = sorted(times)
            mean_ms = sum(times) / len(times)
            p95_ms = times_sorted[int(0.95 * len(times_sorted))]
            err = self._error_rate(rps)
            cpu = self._cpu(rps)
            throughput = rps * (1 - err)
            r = RequestResult(rps=rps, mean_ms=round(mean_ms, 1),
                              p95_ms=round(p95_ms, 1),
                              error_rate=round(err * 100, 2),
                              cpu_pct=round(cpu, 1),
                              throughput=round(throughput, 1))
            results.append(r)
            logger.info(f"  RPS={rps:5d} | mean={r.mean_ms:.0f}ms | "
                        f"p95={r.p95_ms:.0f}ms | err={r.error_rate:.2f}% | CPU={r.cpu_pct:.0f}%")
        return results

    def compare_architectures(self, rps_levels: List[int]) -> Dict:
        """Сравнение монолитной и микросервисной архитектур."""
        # Монолит: выше базовый latency, быстрее насыщается
        monolith = LoadTester()
        monolith.BASE_MS = 150
        monolith.SATURATION_RPS = 350

        micro_results = self.run(rps_levels)
        mono_results = monolith.run(rps_levels, seed=43)

        comparison = []
        for m, mo in zip(micro_results, mono_results):
            improvement_latency = (mo.mean_ms - m.mean_ms) / mo.mean_ms * 100
            comparison.append({
                "rps": m.rps,
                "micro_mean_ms": m.mean_ms,
                "mono_mean_ms": mo.mean_ms,
                "improvement_latency_pct": round(improvement_latency, 1),
                "micro_errors": m.error_rate,
                "mono_errors": mo.error_rate,
            })
        return comparison


# ─── Точка входа ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("НАГРУЗОЧНОЕ ТЕСТИРОВАНИЕ ПРОТОТИПА")
    print("=" * 60)

    tester = LoadTester()
    rps_levels = [50, 100, 200, 500, 1000, 1500]
    results = tester.run(rps_levels)

    print(f"\n{'RPS':>6} | {'Mean(мс)':>9} | {'P95(мс)':>8} | {'Ошибки(%)':>10} | {'CPU(%)':>7}")
    print("-" * 50)
    for r in results:
        print(f"{r.rps:>6} | {r.mean_ms:>9.1f} | {r.p95_ms:>8.1f} | "
              f"{r.error_rate:>10.2f} | {r.cpu_pct:>7.1f}")

    print("\n" + "=" * 60)
    print("СРАВНЕНИЕ АРХИТЕКТУР")
    print("=" * 60)
    comparison = tester.compare_architectures([200, 500, 1000])
    print(f"\n{'RPS':>6} | {'Микросервис(мс)':>16} | {'Монолит(мс)':>12} | {'Прирост(%)':>11}")
    print("-" * 55)
    for c in comparison:
        print(f"{c['rps']:>6} | {c['micro_mean_ms']:>16.1f} | {c['mono_mean_ms']:>12.1f} | "
              f"{c['improvement_latency_pct']:>10.1f}%")

    print("\n" + "=" * 60)
    print("ОБНАРУЖЕНИЕ АНОМАЛИЙ (SVD)")
    print("=" * 60)

    rng = random.Random(7)
    user_activity = {f"u{i}": {
        "posts_per_day": rng.gauss(2, 1),
        "likes_per_day": rng.gauss(10, 3),
        "watch_time": rng.gauss(30, 10),
        "reports_received": rng.gauss(0.1, 0.1),
    } for i in range(1, 21)}
    # Добавляем аномальных пользователей (спам-боты)
    user_activity["bot1"] = {"posts_per_day": 180, "likes_per_day": 500,
                              "watch_time": 0.5, "reports_received": 12}
    user_activity["bot2"] = {"posts_per_day": 95, "likes_per_day": 300,
                              "watch_time": 1.0, "reports_received": 8}

    detector = AnomalyDetector(threshold_percentile=90)
    anomalous, errors = detector.detect_anomalous_users(user_activity)
    print(f"\nАномальные пользователи ({len(anomalous)}): {anomalous}")
    print(f"Порог ошибки реконструкции: {detector.threshold_:.4f}")
    print("\nТоп-5 по ошибке реконструкции:")
    for uid, err in sorted(errors.items(), key=lambda x: x[1], reverse=True)[:5]:
        flag = " ← АНОМАЛИЯ" if uid in anomalous else ""
        print(f"  {uid:8s}: {err:.4f}{flag}")

