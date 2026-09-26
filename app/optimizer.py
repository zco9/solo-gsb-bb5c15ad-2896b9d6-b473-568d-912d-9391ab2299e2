"""一维裁条下料（cutting stock）精确求解。

优化目标（字典序）：
1. 新料使用根数最少；
2. 新料根数相同时，所有已使用原料（新料 + 已动用余料）的尾料总长最少。

锯缝规则：每切下一件扣一次锯缝；当一根原料的末段恰好作为裁件
（尾料为 0）时，最后一次下锯不扣锯缝，即 n 件裁件只扣 n-1 次锯缝。
因此一组裁件能装入长度 S 的原料，当且仅当：
    长度和 + n * 锯缝 <= S        （尾料 >= 0，扣 n 次锯缝）
或  长度和 + (n - 1) * 锯缝 == S  （末段恰好是裁件，扣 n-1 次锯缝）

裁件总数不超过 12 件，对 2^12 个子集做 DP（NumPy 向量化）：
  - g[m]：仅用新料裁出子集 m 的 (最少根数, 该根数下最少尾料)；
  - cost[A]：用余料裁出子集 A 的最小 (已用余料长度和 - 锯缝损耗)，
    则余料侧尾料 = cost[A] - 子集长度和；
  - 合并：min over A of (g_bins[补集], cost[A] - tot[A] + g_left[补集])。
"""

import numpy as np

EPS = 1e-6
MAX_PIECES = 12     # 裁件总件数上限
MAX_REMNANTS = 30   # 余料根数上限
INF_B = 10 ** 9

# 按 n 缓存“与每个掩码不相交的掩码数组”（含 0），总量 3^n，进程内只建一次
_disjoint_cache = {}


def _disjoint_masks(n):
    """返回列表 disj，其中 disj[s] 为所有与 s 不相交的掩码组成的 int32 数组（含 0）。"""
    if n in _disjoint_cache:
        return _disjoint_cache[n]
    N = 1 << n
    full = N - 1
    disj = []
    for s in range(N):
        rest = full ^ s
        arr = [0]
        t = rest
        while t:
            arr.append(t)
            t = (t - 1) & rest
        disj.append(np.array(arr, dtype=np.int32))
    _disjoint_cache[n] = disj
    return disj


def _r(x):
    """保留 3 位小数；整数返回 int，便于前端展示。"""
    v = round(float(x), 3)
    return int(v) if v == int(v) else v


def optimize(stock_length, kerf, remnants, pieces):
    """求解裁切方案。参数与返回值见模块说明及 API 文档。"""
    n = len(pieces)
    if n == 0:
        return {"ok": False, "error": "请至少添加一件裁件。"}
    if n > MAX_PIECES:
        return {"ok": False, "error": f"裁件总数不能超过 {MAX_PIECES} 件。"}

    remnants = sorted((float(r) for r in remnants if r and r > 0), reverse=True)
    if len(remnants) > MAX_REMNANTS:
        return {"ok": False, "error": f"余料根数不能超过 {MAX_REMNANTS} 根。"}

    N = 1 << n
    full = N - 1

    # ---- 子集预处理：件数、长度和、两种装入判定所需的用料长度 ----
    cnt = np.zeros(N, dtype=np.int32)
    tot = np.zeros(N, dtype=np.float64)
    for m in range(1, N):
        lsb = m & -m
        i = lsb.bit_length() - 1
        pm = m ^ lsb
        cnt[m] = cnt[pm] + 1
        tot[m] = tot[pm] + pieces[i]

    need = tot + cnt * kerf                       # 尾料 >= 0 所需原料长度
    exact = tot + (cnt - 1) * kerf                # 恰好放满（末段为裁件）所需长度
    exact[0] = 0.0

    def fits_array(s):
        return (need <= s + EPS) | (np.abs(exact - s) <= EPS)

    def left_over_py(m, s):
        """单个子集的尾料（Python 标量，用于结果展示）。"""
        if float(need[m]) <= s + EPS:
            v = s - float(need[m])
            return v if v > EPS else 0.0
        return 0.0

    def kerf_of_py(m, s):
        if float(need[m]) <= s + EPS:
            return int(cnt[m]) * kerf
        return (int(cnt[m]) - 1) * kerf

    disj = _disjoint_masks(n)

    # ---- 仅用新料的子问题：g[m] = (最少根数, 该根数下最少尾料) ----
    fits_new = fits_array(stock_length)
    left_new = np.where(fits_new, np.clip(stock_length - need, 0.0, None), 0.0)

    g_bins = np.full(N, INF_B, dtype=np.int64)
    g_left = np.full(N, np.inf)
    g_pick = np.zeros(N, dtype=np.int32)
    g_bins[0] = 0
    g_left[0] = 0.0
    for m in range(1, N):
        subs = disj[full ^ m]          # m 的全部子掩码（含 0）
        s_arr = subs[1:]               # 去掉空集
        ok = fits_new[s_arr]
        if not ok.any():
            continue
        s_ok = s_arr[ok]
        prev = m ^ s_ok
        pb = g_bins[prev]
        valid = pb < INF_B
        if not valid.any():
            continue
        s_ok = s_ok[valid]
        prev = prev[valid]
        cb = pb[valid] + 1
        cl = g_left[prev] + left_new[s_ok]
        min_b = cb.min()
        cl = np.where(cb == min_b, cl, np.inf)
        j = int(np.argmin(cl))
        g_bins[m] = min_b
        g_left[m] = cl[j]
        g_pick[m] = s_ok[j]

    # ---- 余料分配：cost[A] = 用余料裁出子集 A 的最小 (已用余料长度和 - 锯缝损耗) ----
    k = len(remnants)
    cost = np.full(N, np.inf)
    cost[0] = 0.0
    parent = np.zeros((k, N), dtype=np.int32)  # parent[i][A]：处理第 i 根余料时为 A 选中的子集（0 表示未用该根）

    for i, r in enumerate(remnants):
        fits_r = fits_array(r)
        fit_list = np.nonzero(fits_r)[0]
        kerf_arr = np.where(need <= r + EPS, cnt * kerf, (cnt - 1) * kerf)
        new_cost = cost.copy()
        for s in fit_list:
            if s == 0:
                continue
            a_arr = disj[s]                       # 与 s 不相交的已有分配
            tgt = a_arr | s
            cand = cost[a_arr] + (r - kerf_arr[s])
            better = cand < new_cost[tgt] - 1e-9
            if better.any():
                tb = tgt[better]
                new_cost[tb] = cand[better]
                parent[i][tb] = s
        cost = new_cost

    # ---- 合并：枚举“由余料裁出的子集 A”，取 (新料根数, 尾料总长) 字典序最小 ----
    comp = full ^ np.arange(N, dtype=np.int32)
    bins_total = g_bins[comp]
    left_total = cost - tot + g_left[comp]
    valid = (bins_total < INF_B) & np.isfinite(cost) & np.isfinite(g_left[comp])

    if not valid.any():
        # 无法裁切：指出超出新料可裁范围、余料也无法容纳的裁件
        over = {}
        for p in pieces:
            if not (p + kerf <= stock_length + EPS or abs(p - stock_length) <= EPS):
                over[p] = over.get(p, 0) + 1
        overlong = [{"length": _r(length), "qty": q} for length, q in sorted(over.items(), reverse=True)]
        return {
            "ok": False,
            "error": "以下裁件超出新料定长的可裁范围，且现有余料无法容纳，请调整裁件或原料。",
            "overlong_pieces": overlong,
        }

    min_bins = bins_total[valid].min()
    cand_a = np.nonzero(valid & (bins_total == min_bins))[0]
    a_best = int(cand_a[np.argmin(left_total[cand_a])])

    # ---- 回溯构造方案 ----
    plans = []
    a = a_best
    for i in range(k - 1, -1, -1):
        s = int(parent[i][a])
        if s:
            plans.append({"source": "remnant", "stock_length": remnants[i], "mask": s})
            a ^= s

    rem = full ^ a_best
    while rem:
        s = int(g_pick[rem])
        plans.append({"source": "new", "stock_length": stock_length, "mask": s})
        rem ^= s

    used_remnant_lengths = [p["stock_length"] for p in plans if p["source"] == "remnant"]
    unused = list(remnants)
    for L in used_remnant_lengths:
        unused.remove(L)

    out_plans = []
    for p in plans:
        mask = p["mask"]
        S = p["stock_length"]
        pl = sorted((pieces[i] for i in range(n) if mask >> i & 1), reverse=True)
        out_plans.append({
            "source": p["source"],
            "stock_length": _r(S),
            "pieces": [_r(x) for x in pl],
            "kerf_loss": _r(kerf_of_py(mask, S)),
            "leftover": _r(left_over_py(mask, S)),
        })

    summary = {
        "new_stock_used": sum(1 for p in out_plans if p["source"] == "new"),
        "remnants_used": sum(1 for p in out_plans if p["source"] == "remnant"),
        "total_kerf_loss": _r(sum(p["kerf_loss"] for p in out_plans)),
        "total_leftover": _r(sum(p["leftover"] for p in out_plans)),
        "piece_count": n,
    }

    return {
        "ok": True,
        "summary": summary,
        "plans": out_plans,
        "unused_remnants": [_r(x) for x in unused],
    }
