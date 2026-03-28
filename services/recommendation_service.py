"""
Гибридная рекомендательная система
Социально-ориентированная веб-система (медицинский домен)

Методы:
  CBF  — контентная фильтрация (TF-IDF + косинусное сходство)
  CF   — коллаборативная фильтрация (SVD-разложение матрицы взаимодействий)
  Hybrid — взвешенное объединение CBF и CF
"""

import math
import random
import logging
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ─── Вспомогательные функции ─────────────────────────────────────────────────
def cosine_similarity(v1: Dict[str, float], v2: Dict[str, float]) -> float:
    """Косинусное сходство двух разреженных векторов."""
    dot = sum(v1.get(k, 0.0) * v for k, v in v2.items())
    norm1 = math.sqrt(sum(x ** 2 for x in v1.values()))
    norm2 = math.sqrt(sum(x ** 2 for x in v2.values()))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def tfidf_vectorize(texts: List[str]) -> List[Dict[str, float]]:
    """Простая TF-IDF векторизация для CBF."""
    import re
    stop = {"и", "в", "не", "на", "с", "что", "это", "как", "по", "а",
            "к", "у", "от", "за", "до", "или", "об", "из", "то", "так"}

    def tokenize(t):
        return [w for w in re.sub(r"[^\w\s]", " ", t.lower()).split()
                if w not in stop and len(w) > 2]

    tokenized = [tokenize(t) for t in texts]
    n = len(texts)
    df: Dict[str, int] = defaultdict(int)
    for tokens in tokenized:
        for term in set(tokens):
            df[term] += 1

    vectors = []
    for tokens in tokenized:
        from collections import Counter
        tf = Counter(tokens)
        n_tok = len(tokens) or 1
        vec = {}
        for term, cnt in tf.items():
            idf = math.log((1 + n) / (1 + df[term])) + 1
            vec[term] = (cnt / n_tok) * idf
        vectors.append(vec)
    return vectors


# ─── Контентная фильтрация (CBF) ─────────────────────────────────────────────
class ContentBasedFilter:
    """
    Рекомендации на основе схожести контента публикаций.
    Использует TF-IDF представление текстов и косинусное сходство.
    """

    def __init__(self):
        self.item_ids: List[str] = []
        self.item_vectors: List[Dict[str, float]] = []
        self.item_meta: Dict[str, dict] = {}

    def fit(self, items: List[dict]):
        """
        items: список словарей с полями 'id', 'title', 'content', 'tags'
        """
        self.item_ids = [it["id"] for it in items]
        texts = [f"{it['title']} {it.get('content', '')} {' '.join(it.get('tags', []))}"
                 for it in items]
        self.item_vectors = tfidf_vectorize(texts)
        self.item_meta = {it["id"]: it for it in items}
        logger.info(f"CBF fitted: {len(items)} items")
        return self

    def recommend(self, item_id: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """Рекомендации похожих публикаций по одной публикации."""
        if item_id not in self.item_ids:
            return []
        idx = self.item_ids.index(item_id)
        query_vec = self.item_vectors[idx]
        scores = []
        for i, vec in enumerate(self.item_vectors):
            if i == idx:
                continue
            sim = cosine_similarity(query_vec, vec)
            scores.append((self.item_ids[i], sim))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def recommend_for_user(self, liked_ids: List[str], top_k: int = 10) -> List[Tuple[str, float]]:
        """Рекомендации пользователю на основе просмотренных публикаций."""
        if not liked_ids:
            return []
        # Профиль пользователя = среднее TF-IDF всех понравившихся
        user_vec: Dict[str, float] = defaultdict(float)
        valid = 0
        for iid in liked_ids:
            if iid in self.item_ids:
                idx = self.item_ids.index(iid)
                for term, val in self.item_vectors[idx].items():
                    user_vec[term] += val
                valid += 1
        if valid == 0:
            return []
        user_vec = {k: v / valid for k, v in user_vec.items()}

        seen = set(liked_ids)
        scores = []
        for i, iid in enumerate(self.item_ids):
            if iid in seen:
                continue
            sim = cosine_similarity(dict(user_vec), self.item_vectors[i])
            scores.append((iid, sim))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


# ─── SVD-разложение матрицы взаимодействий ───────────────────────────────────
class SVDRecommender:
    """
    Коллаборативная фильтрация на основе усечённого SVD.
    Реализация: Power Iteration для нахождения k главных компонент.
    Для реального использования заменить на scipy.sparse.linalg.svds.
    """

    def __init__(self, n_factors: int = 20, n_iter: int = 15, lr: float = 0.005,
                 reg: float = 0.02, epochs: int = 30):
        self.n_factors = n_factors
        self.n_iter = n_iter
        self.lr = lr
        self.reg = reg
        self.epochs = epochs
        self.user_ids: List[str] = []
        self.item_ids: List[str] = []
        self.user_factors: List[List[float]] = []
        self.item_factors: List[List[float]] = []
        self.global_mean: float = 0.0
        self.user_bias: List[float] = []
        self.item_bias: List[float] = []

    def _init_factors(self, n: int) -> List[List[float]]:
        rng = random.Random(42)
        return [[rng.gauss(0, 0.1) for _ in range(self.n_factors)] for _ in range(n)]

    def fit(self, interactions: List[dict]):
        """
        interactions: [{"user_id": str, "item_id": str, "rating": float}, ...]
        rating: 1.0 (просмотр), 2.0 (лайк), 3.0 (комментарий)
        """
        # Индексация
        self.user_ids = list({r["user_id"] for r in interactions})
        self.item_ids = list({r["item_id"] for r in interactions})
        uid_map = {u: i for i, u in enumerate(self.user_ids)}
        iid_map = {it: i for i, it in enumerate(self.item_ids)}

        n_users = len(self.user_ids)
        n_items = len(self.item_ids)

        self.global_mean = sum(r["rating"] for r in interactions) / len(interactions)
        self.user_factors = self._init_factors(n_users)
        self.item_factors = self._init_factors(n_items)
        self.user_bias = [0.0] * n_users
        self.item_bias = [0.0] * n_items

        # SGD обучение
        for epoch in range(self.epochs):
            random.shuffle(interactions)
            total_loss = 0.0
            for r in interactions:
                u = uid_map[r["user_id"]]
                i = iid_map[r["item_id"]]
                rating = r["rating"]

                # Предсказание
                pred = (self.global_mean + self.user_bias[u] + self.item_bias[i] +
                        sum(self.user_factors[u][f] * self.item_factors[i][f]
                            for f in range(self.n_factors)))
                err = rating - pred
                total_loss += err ** 2

                # Обновление смещений
                self.user_bias[u] += self.lr * (err - self.reg * self.user_bias[u])
                self.item_bias[i] += self.lr * (err - self.reg * self.item_bias[i])

                # Обновление факторов
                for f in range(self.n_factors):
                    uf = self.user_factors[u][f]
                    itf = self.item_factors[i][f]
                    self.user_factors[u][f] += self.lr * (err * itf - self.reg * uf)
                    self.item_factors[i][f] += self.lr * (err * uf - self.reg * itf)

            if epoch % 10 == 0:
                rmse = math.sqrt(total_loss / len(interactions))
                logger.debug(f"SVD epoch {epoch}: RMSE={rmse:.4f}")

        logger.info(f"SVD fitted: {n_users} users, {n_items} items, {self.n_factors} factors")
        return self

    def predict(self, user_id: str, item_id: str) -> float:
        if user_id not in self.user_ids or item_id not in self.item_ids:
            return self.global_mean
        u = self.user_ids.index(user_id)
        i = self.item_ids.index(item_id)
        return (self.global_mean + self.user_bias[u] + self.item_bias[i] +
                sum(self.user_factors[u][f] * self.item_factors[i][f]
                    for f in range(self.n_factors)))

    def recommend(self, user_id: str, seen_items: List[str],
                  top_k: int = 10) -> List[Tuple[str, float]]:
        if user_id not in self.user_ids:
            return []
        seen = set(seen_items)
        scores = []
        for item_id in self.item_ids:
            if item_id not in seen:
                scores.append((item_id, self.predict(user_id, item_id)))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


# ─── Гибридная рекомендательная система ──────────────────────────────────────
class HybridRecommender:
    """
    Объединяет CBF и SVD по схеме взвешенного голосования.
    alpha — вес CBF, (1-alpha) — вес SVD.
    """

    def __init__(self, alpha: float = 0.4):
        self.alpha = alpha
        self.cbf = ContentBasedFilter()
        self.svd = SVDRecommender(n_factors=15, epochs=25)
        self._fitted = False

    def fit(self, items: List[dict], interactions: List[dict]):
        self.cbf.fit(items)
        self.svd.fit(interactions)
        self._fitted = True
        logger.info(f"HybridRecommender fitted (alpha={self.alpha})")
        return self

    def recommend(self, user_id: str, liked_ids: List[str],
                  top_k: int = 10) -> List[dict]:
        assert self._fitted, "Call fit() first"

        # Нормализация CBF-скоров
        cbf_raw = self.cbf.recommend_for_user(liked_ids, top_k=top_k * 2)
        cbf_max = max((s for _, s in cbf_raw), default=1.0) or 1.0
        cbf_scores = {iid: s / cbf_max for iid, s in cbf_raw}

        # Нормализация SVD-скоров
        svd_raw = self.svd.recommend(user_id, liked_ids, top_k=top_k * 2)
        svd_max = max((s for _, s in svd_raw), default=1.0) or 1.0
        svd_scores = {iid: s / svd_max for iid, s in svd_raw}

        # Объединение всех кандидатов
        all_ids = set(cbf_scores) | set(svd_scores)
        combined = []
        for iid in all_ids:
            score = (self.alpha * cbf_scores.get(iid, 0.0) +
                     (1 - self.alpha) * svd_scores.get(iid, 0.0))
            combined.append({"item_id": iid, "score": round(score, 4),
                              "cbf_score": round(cbf_scores.get(iid, 0.0), 4),
                              "svd_score": round(svd_scores.get(iid, 0.0), 4)})

        combined.sort(key=lambda x: x["score"], reverse=True)
        return combined[:top_k]

    def evaluate_metrics(self, test_interactions: List[dict]) -> Dict:
        """
        Precision@K, Recall@K, NDCG@K на тестовой выборке.
        """
        K = 5
        precisions, recalls, ndcgs = [], [], []

        # Группировка по пользователю
        user_test: Dict[str, List[str]] = defaultdict(list)
        for r in test_interactions:
            if r["rating"] >= 2.0:  # лайк или комментарий = релевантно
                user_test[r["user_id"]].append(r["item_id"])

        for user_id, relevant in user_test.items():
            history = [r["item_id"] for r in test_interactions
                       if r["user_id"] == user_id and r["item_id"] not in relevant]
            recs = self.recommend(user_id, history, top_k=K)
            rec_ids = [r["item_id"] for r in recs]

            hits = [1 if iid in relevant else 0 for iid in rec_ids]
            prec = sum(hits) / K
            rec = sum(hits) / max(len(relevant), 1)

            # NDCG
            ideal_dcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(relevant), K)))
            dcg = sum(hits[i] / math.log2(i + 2) for i in range(K))
            ndcg = dcg / ideal_dcg if ideal_dcg > 0 else 0.0

            precisions.append(prec)
            recalls.append(rec)
            ndcgs.append(ndcg)

        return {
            f"Precision@{K}": round(sum(precisions) / len(precisions), 4) if precisions else 0,
            f"Recall@{K}": round(sum(recalls) / len(recalls), 4) if recalls else 0,
            f"NDCG@{K}": round(sum(ndcgs) / len(ndcgs), 4) if ndcgs else 0,
            "users_evaluated": len(precisions),
        }


# ─── Генерация демо-данных ────────────────────────────────────────────────────
def generate_demo_data():
    items = [
        {"id": "p1", "title": "Лечение гипертонии: современные препараты",
         "content": "Гипертония требует комплексного лечения с применением антигипертензивных препаратов",
         "tags": ["кардиология", "лечение", "препараты"]},
        {"id": "p2", "title": "Диабет 2 типа: диета и контроль глюкозы",
         "content": "Контроль уровня глюкозы крови при диабете 2 типа",
         "tags": ["диабет", "диета", "эндокринология"]},
        {"id": "p3", "title": "Реабилитация после инфаркта",
         "content": "Программа кардиореабилитации после перенесённого инфаркта миокарда",
         "tags": ["кардиология", "реабилитация"]},
        {"id": "p4", "title": "Антибиотики при пневмонии",
         "content": "Выбор антибактериальной терапии при внебольничной пневмонии",
         "tags": ["пульмонология", "антибиотики"]},
        {"id": "p5", "title": "Симптомы дефицита витамина D",
         "content": "Клинические проявления и лечение дефицита витамина D",
         "tags": ["витамины", "дефицит"]},
        {"id": "p6", "title": "МРТ при болях в спине",
         "content": "Показания и интерпретация МРТ поясничного отдела позвоночника",
         "tags": ["неврология", "диагностика", "МРТ"]},
        {"id": "p7", "title": "Профилактика ОРВИ у детей",
         "content": "Методы профилактики острых респираторных вирусных инфекций у детей",
         "tags": ["педиатрия", "профилактика"]},
        {"id": "p8", "title": "Операция по замене тазобедренного сустава",
         "content": "Показания, подготовка и восстановление после эндопротезирования",
         "tags": ["ортопедия", "операция", "реабилитация"]},
    ]

    random.seed(42)
    users = [f"u{i}" for i in range(1, 11)]
    interactions = []
    for user in users:
        n_interact = random.randint(3, 7)
        for _ in range(n_interact):
            item = random.choice(items)
            rating = random.choice([1.0, 1.0, 2.0, 3.0])
            interactions.append({
                "user_id": user,
                "item_id": item["id"],
                "rating": rating,
            })
    return items, interactions


# ─── Точка входа ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    items, interactions = generate_demo_data()

    # Разделение train/test
    split = int(len(interactions) * 0.8)
    train_interactions = interactions[:split]
    test_interactions = interactions[split:]

    recommender = HybridRecommender(alpha=0.4)
    recommender.fit(items, train_interactions)

    print("\n" + "=" * 60)
    print("ГИБРИДНАЯ РЕКОМЕНДАТЕЛЬНАЯ СИСТЕМА — ТЕСТ")
    print("=" * 60)

    # Пример рекомендаций для пользователя
    liked = ["p1", "p3"]
    recs = recommender.recommend("u1", liked_ids=liked, top_k=5)
    print(f"\nРекомендации для u1 (просмотрел: {liked}):")
    for r in recs:
        meta = {it["id"]: it["title"] for it in items}
        print(f"  {r['item_id']:4s} | score={r['score']:.4f} "
              f"(cbf={r['cbf_score']:.3f}, svd={r['svd_score']:.3f}) "
              f"| {meta.get(r['item_id'], '—')}")

    metrics = recommender.evaluate_metrics(test_interactions)
    print("\nМЕТРИКИ КАЧЕСТВА:")
    for k, v in metrics.items():
        print(f"  {k}: {v}")

