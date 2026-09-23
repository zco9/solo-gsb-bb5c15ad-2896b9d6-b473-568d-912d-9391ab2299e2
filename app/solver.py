"""木作裁条排样求解器。

锯缝计量规则：
- 每切下一件裁件扣一次锯缝；
- 当一根原料的最后一段恰好作为裁件（尾料为 0）时，该最后一件不另扣锯缝。

因此一根原料上排 k 件、裁件长之和为 S：
- 常规（留有尾料或末段仍锯切）：占用 = S + k * kerf，尾料 = L - 占用 >= 0；
- 末段恰好作为裁件：占用 = S + (k - 1) * kerf = L，尾料 = 0。

优化目标（字典序）：
1. 使用的新料根数最少；
2. 新料根数相同时，所有已动用原料（已用余料 + 已用新料）的尾料总长最少。
   未动用的余料不计入尾料。

裁件总数不超过 12，采用子集 DP 精确求解（复杂度约 3^N），
任何排法都按上述占用规则校验，不会把装不下的裁件硬塞进原料。
"""
from __future__ import annotations

from dataclasses import dataclass, field

EPS = 1e-6

MAX_TOTAL_PIECES = 12
MAX_LEFTOVERS = 30


def _r(x: float) -> float:
    """输出规整：最多 3 位小数，接近整数时返回整数。"""
    x = round(float(x), 3)
    return int(x) if abs(x - round(x)) < 1e-9 else x


@dataclass(frozen=True)
class PieceItem:
    length: float
    seq: int      # 同长度裁件中的序号（从 1 开始）
    order: int    # 输入行号（用于标注超长裁件）


@dataclass
class PlanPiece:
    length: float
    seq: int
    order: int


@dataclass
class BarPlan:
    bar_type: str             # "new" 或 "leftover"
    bar_length: float
    bar_index: int            # 余料输入序号（1 起）；新料为 0
    new_index: int = 0        # 新料序号（1 起）
    pieces: list[PlanPiece] = field(default_factory=list)
    kerf_loss: float = 0.0
    tail: float = 0.0
    exact_last: bool = False  # 末段是否恰好作为裁件（零尾料、免末道锯缝）


@dataclass
class SolveResult:
    feasible: bool
    bars: list[BarPlan] = field(default_factory=list)
    unused_leftover_indices: list[int] = field(default_factory=list)
    overlong: list[dict] = field(default_factory=list)
    new_bar_count: int = 0
    used_leftover_count: int = 0
    total_tail: float = 0.0
    total_kerf: float = 0.0
    total_piece_length: float = 0.0
    bar_count: int = 0
    message: str = ""


def solve(
    new_length: float,
    leftover_lengths: list[float],
    kerf: float,
    piece_rows: list[tuple[float, int]],
) -> SolveResult:
    # ---- 展开裁件 ----
    pieces: list[PieceItem] = []
    total_piece_length = 0.0
    for order, (length, qty) in enumerate(piece_rows, start=1):
        for seq in range(1, qty + 1):
            pieces.append(PieceItem(length=length, seq=seq, order=order))
            total_piece_length += length

    n = len(pieces)

    max_stock = max(leftover_lengths + [new_length])

    # ---- 单件超长检查（连一道锯缝都排不下，且不等于最长料的整根长度）----
    overlong_map: dict[int, float] = {}
    for p in pieces:
        single_ok = (p.length + kerf <= max_stock + EPS) or (
            abs(p.length - max_stock) <= EPS
        )
        if not single_ok:
            overlong_map[p.order] = p.length
    if overlong_map:
        return SolveResult(
            feasible=False,
            overlong=[
                {"order": o, "length": _r(l)}
                for o, l in sorted(overlong_map.items())
            ],
            total_piece_length=_r(total_piece_length),
            message="存在超长裁件，任何原料都无法裁切。",
        )

    # ---- 裁件按长度降序排列，所有位掩码均在该排序空间内运算 ----
    order_sorted = sorted(range(n), key=lambda i: -pieces[i].length)
    orig_of = order_sorted  # sorted 位 j -> 原始裁件下标
    plen = [pieces[orig].length for orig in orig_of]

    all_mask = (1 << n) - 1

    def subset_total(mask: int) -> tuple[float, int]:
        total = 0.0
        k = 0
        m = mask
        while m:
            b = m & -m
            i = b.bit_length() - 1
            total += plen[i]
            k += 1
            m ^= b
        return total, k

    def enumerate_feasible(stock_len: float) -> dict[int, tuple[float, bool]]:
        """枚举一根该长度原料能排的所有非空裁件子集。

        返回 {mask: (尾料, 是否末段恰为裁件)}。
        按长度从大到小递归：常规容量超界后仅检查 exact（恰好零尾料）即剪枝。
        """
        result: dict[int, tuple[float, bool]] = {}

        def rec(i: int, chosen: int, total: float, k: int) -> None:
            if k and total + k * kerf > stock_len + EPS:
                # 常规排法已超界；仅当当前集合恰好排满（k-1 道锯缝）才可行，
                # 且不能再加入任何裁件。
                if abs(total + (k - 1) * kerf - stock_len) <= EPS:
                    result[chosen] = (0.0, True)
                return
            if i == n:
                if k:
                    tail = stock_len - (total + k * kerf)
                    if tail < 0:
                        tail = 0.0
                    result[chosen] = (tail, False)
                return
            # 不选第 i 件
            rec(i + 1, chosen, total, k)
            # 选第 i 件
            rec(i + 1, chosen | (1 << i), total + plen[i], k + 1)

        rec(0, 0, 0.0, 0)
        return result

    feasible_new = enumerate_feasible(new_length)
    all_feasible_lefts = [enumerate_feasible(L) for L in leftover_lengths]

    # 连一件裁件都放不下的余料不可能被使用，直接判为未动用、不进入 DP
    relevant: list[tuple[int, dict]] = []
    for idx, feats in enumerate(all_feasible_lefts):
        if feats:
            relevant.append((idx, feats))

    def _merge(state: dict[int, float], mask: int, tail: float) -> None:
        """状态合并：同一剩余掩码只保留最小尾料。"""
        old = state.get(mask)
        if old is None or tail < old:
            state[mask] = tail

    def _apply_bar(
        layer: dict[int, float], feats: dict[int, tuple[float, bool]]
    ) -> dict[int, float]:
        """对一层状态叠加一根原料：每个状态可以不动用它，或用它排一个可行子集。

        返回新一层 {剩余掩码: 最小累计尾料}。两种遍历方式取成本较低者：
        - A：枚举每个状态剩余掩码的子掩码；
        - B：枚举该料的可行子集，逐个测试是否被状态包含。
        """
        nxt = dict(layer)  # 不动用这根料
        subs = list(feats.keys())
        cost_a = sum(1 << mask.bit_count() for mask in layer)
        cost_b = len(layer) * len(subs)
        if cost_b < cost_a:
            for mask, cur_tail in layer.items():
                if mask == 0:
                    continue
                for sub in subs:
                    if sub & ~mask == 0:
                        _merge(nxt, mask ^ sub, cur_tail + feats[sub][0])
        else:
            for mask, cur_tail in layer.items():
                if mask == 0:
                    continue
                sub = mask
                while sub:
                    info = feats.get(sub)
                    if info is not None:
                        _merge(nxt, mask ^ sub, cur_tail + info[0])
                    sub = (sub - 1) & mask
        return nxt

    # ---- 逐层通过相关余料，保存每层快照用于回溯 ----
    # 按料长降序处理：长料先消耗更多裁件，状态更快收敛；原始序号保留用于展示。
    relevant.sort(key=lambda rf: -leftover_lengths[rf[0]])
    left_layers: list[dict[int, float]] = [{all_mask: 0.0}]
    for orig_idx, feats in relevant:
        left_layers.append(_apply_bar(left_layers[-1], feats))

    # ---- 之后只加新料，第 k 层表示至多动用 k 根新料；最先出现 0 掩码即最少根数 ----
    # k=0：仅靠余料即可完成
    best_new_count = 0 if 0 in left_layers[-1] else None
    best_tail = left_layers[-1].get(0) if best_new_count == 0 else None
    new_layers: list[dict[int, float]] = [left_layers[-1]]
    if best_new_count is None:
        for k in range(1, n + 1):
            new_layers.append(_apply_bar(new_layers[-1], feasible_new))
            t0 = new_layers[k].get(0)
            if t0 is not None:
                best_new_count = k
                best_tail = t0
                break

    if best_new_count is None:
        return SolveResult(
            feasible=False,
            total_piece_length=_r(total_piece_length),
            message="当前原料组合无法完成裁切，请检查输入参数。",
        )

    # ---- 回溯：先沿新料层回退，再沿余料层回退 ----
    def _prev_option(
        prev_layer: dict[int, float],
        feats: dict[int, tuple[float, bool]],
        target_mask: int,
        target_tail: float,
    ):
        """找到从 prev_layer 经一根料到达 (target_mask, target_tail) 的来源。

        返回 (prev_mask, chosen_sub)；chosen_sub 为 0 表示未动用该料。
        """
        # 未动用
        pv = prev_layer.get(target_mask)
        if pv is not None and abs(pv - target_tail) <= EPS:
            return target_mask, 0
        # 动用：prev_mask = target_mask | sub，尾料满足 pv + tail(sub) = target
        # 来源状态必然包含 target_mask；枚举 prev 中额外的位集合（来自已消耗位）
        extra = all_mask ^ target_mask
        m = extra
        while True:
            prev_mask = target_mask | m
            pv = prev_layer.get(prev_mask)
            if pv is not None and m:
                info = feats.get(m)
                if info is not None and abs(pv + info[0] - target_tail) <= EPS:
                    return prev_mask, m
            if m == 0:
                break
            m = (m - 1) & extra
        raise RuntimeError("回溯失败")

    chosen_new: list[int] = []
    target_mask = 0
    target_tail = best_tail
    for k in range(best_new_count, 0, -1):
        prev_mask, sub = _prev_option(new_layers[k - 1], feasible_new,
                                      target_mask, target_tail)
        chosen_new.append(sub)
        target_mask, target_tail = prev_mask, new_layers[k - 1][prev_mask]
    chosen_new.reverse()
    # 此时 target_mask/target_tail 是余料阶段结束后的状态

    chosen_left: list[tuple[int, int]] = []
    for i in range(len(relevant) - 1, -1, -1):
        orig_idx, feats = relevant[i]
        prev_mask, sub = _prev_option(left_layers[i], feats,
                                      target_mask, target_tail)
        if sub:
            chosen_left.append((orig_idx, sub))
        target_mask, target_tail = prev_mask, left_layers[i][prev_mask]
    chosen_left.reverse()

    used_left = chosen_left
    new_masks = [m for m in chosen_new if m]
    assert target_mask == all_mask

    # ---- 组装逐根方案 ----
    def display_indices(mask_sorted: int) -> list[int]:
        idxs: list[int] = []
        m = mask_sorted
        while m:
            b = m & -m
            idxs.append(orig_of[b.bit_length() - 1])
            m ^= b
        idxs.sort(key=lambda x: (-pieces[x].length, pieces[x].order, pieces[x].seq))
        return idxs

    bars: list[BarPlan] = []
    total_tail = 0.0
    total_kerf = 0.0

    for left_i, mask_sorted in used_left:
        L = leftover_lengths[left_i]
        total, k = subset_total(mask_sorted)
        _, exact = all_feasible_lefts[left_i][mask_sorted]
        idxs = display_indices(mask_sorted)
        kerf_loss = (k - 1) * kerf if exact else k * kerf
        tail = 0.0 if exact else max(0.0, L - total - k * kerf)
        bars.append(BarPlan(
            bar_type="leftover",
            bar_length=L,
            bar_index=left_i + 1,
            pieces=[PlanPiece(pieces[x].length, pieces[x].seq, pieces[x].order) for x in idxs],
            kerf_loss=kerf_loss,
            tail=tail,
            exact_last=exact,
        ))
        total_tail += tail
        total_kerf += kerf_loss

    for j, mask_sorted in enumerate(new_masks, start=1):
        L = new_length
        total, k = subset_total(mask_sorted)
        _, exact = feasible_new[mask_sorted]
        idxs = display_indices(mask_sorted)
        kerf_loss = (k - 1) * kerf if exact else k * kerf
        tail = 0.0 if exact else max(0.0, L - total - k * kerf)
        bars.append(BarPlan(
            bar_type="new",
            bar_length=L,
            bar_index=0,
            new_index=j,
            pieces=[PlanPiece(pieces[x].length, pieces[x].seq, pieces[x].order) for x in idxs],
            kerf_loss=kerf_loss,
            tail=tail,
            exact_last=exact,
        ))
        total_tail += tail
        total_kerf += kerf_loss

    bars.sort(key=lambda b: (
        0 if b.bar_type == "leftover" else 1,
        b.bar_index if b.bar_type == "leftover" else b.new_index,
    ))

    used_set = {i for i, _ in used_left}
    unused = sorted(
        i + 1 for i in range(len(leftover_lengths)) if i not in used_set
    )

    return SolveResult(
        feasible=True,
        bars=bars,
        unused_leftover_indices=unused,
        new_bar_count=len(new_masks),
        used_leftover_count=len(used_left),
        total_tail=_r(total_tail),
        total_kerf=_r(total_kerf),
        total_piece_length=_r(total_piece_length),
        bar_count=len(bars),
    )
