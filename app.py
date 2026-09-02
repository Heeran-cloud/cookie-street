
import streamlit as st
from collections import defaultdict
from itertools import combinations
from math import gcd
from time import perf_counter

st.set_page_config(page_title="Cookie Street", page_icon="🍪", layout="wide")

DEFAULT_PRODUCTS = [
    ("오레오", 1800, 12), ("초코칩쿠키", 2500, 8), ("화이트하임", 3200, 5), ("초코하임", 4500, 6),
    ("몽쉘", 5500, 4), ("뽀또", 3800, 3), ("에이스", 6200, 2), ("애플파이", 4900, 3),
    ("초코송이", 2450, 2), ("고래밥", 2800, 1), ("포카칩", 3300, 2), ("초코파이", 3700, 4),
]

st.title("🍪 Cookie Street")
st.caption(
    "목표금액은 반드시 정확히 맞춥니다. 사진 수는 프로그램이 자동으로 결정하며, "
    "각 사진에는 최소 10개의 과자가 들어갑니다."
)
# ---------------------------------------------------------
# Footer Logo
# ---------------------------------------------------------


# ============================================================
# 입력
# ============================================================
st.subheader("설정")
c1, c2 = st.columns(2)
with c1:
    budget = st.number_input("기존 예산 (원)", min_value=1, value=300000, step=1000)
with c2:
    min_items = st.number_input("사진당 최소 과자 수", min_value=10, value=10, step=1)

st.subheader("현재 보유 제품")
rows = st.data_editor(
    [{"상품": n, "단가": p, "보유수량": q} for n, p, q in DEFAULT_PRODUCTS],
    use_container_width=True,
    hide_index=True,
    num_rows="dynamic",
    column_config={
        "상품": st.column_config.TextColumn("상품", width="small"),
        "단가": st.column_config.NumberColumn("단가", min_value=1, step=100),
        "보유수량": st.column_config.NumberColumn("보유수량", min_value=0, step=1),
    },
)

def normalize_products(rows):
    result = []
    for row in rows:
        name = str(row.get("상품", "")).strip()
        try:
            price = int(row.get("단가", 0))
            qty = int(row.get("보유수량", 0))
        except (TypeError, ValueError):
            continue
        if name and price > 0 and qty > 0:
            result.append((name, price, qty))
    return result

products = normalize_products(rows)
budget = int(budget)
min_items = int(min_items)
inventory_total = sum(price * qty for _, price, qty in products)

s1, s2, s3 = st.columns(3)
s1.metric("기존 예산", f"{budget:,}원")
s2.metric("현재 제품 총액", f"{inventory_total:,}원")
delta = inventory_total - budget
if delta >= 0:
    s3.metric("예산 대비 보유액", f"+{delta:,}원")
else:
    s3.metric("예산 대비 부족액", f"{-delta:,}원")

# ============================================================
# 정확한 사진 조합 생성
# ============================================================
def gcd_all(values):
    g = 0
    for value in values:
        g = gcd(g, int(value))
    return g

def add_candidate(bucket, counts, max_candidates):
    """Amount별로 소수의 서로 다른 패턴만 유지."""
    bucket.append(tuple(counts))
    if len(bucket) <= max_candidates:
        return

    # 서로 다른 상품을 많이 쓰고, 한 상품에 지나치게 몰리지 않는 패턴 우선.
    def quality(c):
        distinct = sum(q > 0 for q in c)
        max_q = max(c) if c else 0
        total_items = sum(c)
        return (distinct, -max_q, -total_items)

    unique = list(dict.fromkeys(bucket))
    unique.sort(key=quality, reverse=True)
    del bucket[:]
    bucket.extend(unique[:max_candidates])

def generate_photo_options(products, target, min_items, max_patterns=8):
    """
    한 장의 사진으로 만들 수 있는 '정확한 금액' 후보를 생성한다.
    금액은 전체 단가의 gcd 단위로 축소하여 상태 수를 크게 줄인다.

    dp[amount] = (최대 item_count, [여러 count pattern])
    """
    prices = [p for _, p, _ in products]
    scale = gcd_all(prices + [target])
    if scale <= 0 or target % scale != 0:
        return None, scale

    target_u = target // scale
    steps = [p // scale for p in prices]
    n = len(products)

    # amount -> {pattern: item_count}
    dp = {0: {(0,) * n: 0}}

    for i, (_, _, max_qty) in enumerate(products):
        step = steps[i]
        new = {}

        for amount, patterns in dp.items():
            for pattern, item_count in patterns.items():
                max_q = min(max_qty, (target_u - amount) // step)
                for q in range(max_q + 1):
                    new_amount = amount + step * q
                    new_items = item_count + q
                    if new_amount > target_u:
                        break

                    new_pattern = list(pattern)
                    new_pattern[i] = q
                    new_pattern = tuple(new_pattern)

                    bucket = new.setdefault(new_amount, {})
                    # 같은 amount에서 너무 많은 패턴이 쌓이지 않게 유지.
                    old = bucket.get(new_pattern)
                    if old is None or new_items > old:
                        bucket[new_pattern] = new_items

        # 상태 폭발 방지: amount별로 최대 패턴 수만 유지.
        # 정확한 금액 자체는 버리지 않고, 같은 amount의 표현만 압축한다.
        for amount, patterns in list(new.items()):
            items = list(patterns.items())

            def quality(item):
                pattern, count = item
                distinct = sum(q > 0 for q in pattern)
                max_q = max(pattern) if pattern else 0
                return (distinct, -max_q, count)

            items.sort(key=quality, reverse=True)
            new[amount] = dict(items[:max_patterns])

        dp = new

    options = {}
    for amount_u, patterns in dp.items():
        valid = [
            pattern
            for pattern, item_count in patterns.items()
            if item_count >= min_items and amount_u > 0
        ]
        if valid:
            options[amount_u] = valid

    return options, scale

def find_amount_partitions(amounts, target_u, photo_count, limit=250):
    """
    정확히 target_u가 되도록 photo_count개의 사진 금액을 찾는다.
    금액 조합은 오름차순으로만 탐색하여 순열 중복을 제거한다.
    """
    amounts = sorted(a for a in amounts if a > 0 and a <= target_u)
    amount_set = set(amounts)
    result = []

    def dfs(start_idx, remaining, left, path):
        if len(result) >= limit:
            return

        if left == 1:
            if remaining in amount_set and remaining >= (path[-1] if path else 0):
                result.append(tuple(path + [remaining]))
            return

        if remaining <= 0:
            return

        min_allowed = path[-1] if path else amounts[0]

        # 각 남은 사진이 현재 값 이상이어야 하므로 현재 값 <= remaining/left.
        upper = remaining // left

        for idx in range(start_idx, len(amounts)):
            a = amounts[idx]
            if a < min_allowed:
                continue
            if a > upper:
                break

            # 남은 left-1개가 최소한 a 이상이어야 한다.
            if remaining - a < a * (left - 1):
                continue

            dfs(idx, remaining - a, left - 1, path + [a])

            if len(result) >= limit:
                return

    dfs(0, target_u, photo_count, [])
    return result

def pattern_overlap(a, b):
    overlap_products = 0
    overlap_units = 0
    for x, y in zip(a, b):
        if x and y:
            overlap_products += 1
            overlap_units += min(x, y)
    return overlap_products, overlap_units

def diversity_score(patterns):
    score = 0
    for a, b in combinations(patterns, 2):
        p, q = pattern_overlap(a, b)
        score += p * 100 + q * 10
    return score

def choose_patterns(partition, options, photo_count, max_combos=50000):
    """
    각 금액별 후보 패턴 중 사진 간 중복도가 가장 낮은 조합을 선택한다.
    """
    candidate_lists = [options[a] for a in partition]
    best = None
    best_score = None
    checked = 0

    # DFS + branch-and-bound 성격의 간단한 beam.
    beam = [([], 0)]
    beam_width = 300

    for candidates in candidate_lists:
        next_beam = []
        for chosen, score in beam:
            for pattern in candidates:
                checked += 1
                incremental = 0
                for old in chosen:
                    p, q = pattern_overlap(old, pattern)
                    incremental += p * 100 + q * 10
                next_beam.append((chosen + [pattern], score + incremental))

                if checked >= max_combos:
                    break
            if checked >= max_combos:
                break

        next_beam.sort(key=lambda x: x[1])
        beam = next_beam[:beam_width]

    if beam:
        best = beam[0][0]
        best_score = beam[0][1]

    return best, best_score

def exact_cookie_solver(products, budget, min_items):
    """
    정확성을 최우선으로 하는 자동 사진 수 결정.
    1~10장까지 순차적으로 검사하되, 3장을 우선한다.
    3장이 가능한 경우 3장 중 다양성이 가장 좋은 후보를 선택하고,
    3장이 불가능하면 2장 -> 4장 -> 5장 ... 순으로 확장한다.

    같은 상품은 다른 사진에 다시 등장할 수 있다.
    상품별 보유수량은 각 사진 안에서만 제한된다.
    """
    if not products:
        return None

    prices = [p for _, p, _ in products]
    scale = gcd_all(prices + [budget])
    if scale <= 0 or budget % scale != 0:
        return None

    options, scale = generate_photo_options(
        products, budget, min_items, max_patterns=8
    )
    if not options:
        return None

    target_u = budget // scale
    available_amounts = sorted(options.keys())

    # 목표에 따라 필요한 최소/최대 사진 수를 빠르게 제한.
    min_photo_amount = min(available_amounts)
    max_photo_amount = max(available_amounts)
    max_possible_photos = min(10, target_u // min_photo_amount)

    # 기본 선호: 3장.
    order = [3, 2, 4, 5, 6, 7, 8, 9, 10, 1]
    order = [k for k in order if k <= max_possible_photos]

    for k in order:
        # k장으로 가능한 금액 분할을 정확히 찾는다.
        partitions = find_amount_partitions(
            available_amounts, target_u, k, limit=350
        )
        if not partitions:
            continue

        best_plan = None
        best_score = None

        # 첫 후보만 쓰지 않고 여러 금액 분할을 평가한다.
        for partition in partitions:
            patterns, score = choose_patterns(
                partition, options, k, max_combos=50000
            )
            if patterns is None:
                continue

            if best_score is None or score < best_score:
                best_score = score
                best_plan = (partition, patterns)

        if best_plan:
            return best_plan, scale, k

    return None

# ============================================================
# 계산
# ============================================================
if "result" not in st.session_state:
    st.session_state.result = None
if "elapsed" not in st.session_state:
    st.session_state.elapsed = None

st.divider()

if st.button("🍪 최적 조합 계산하기", type="primary", use_container_width=True):
    if not products:
        st.error("상품을 1개 이상 입력해주세요.")
        st.stop()

    start = perf_counter()

    with st.spinner("정확한 금액의 최적 사진 조합을 계산하고 있습니다..."):
        solved = exact_cookie_solver(products, budget, min_items)

    elapsed = perf_counter() - start
    st.session_state.result = solved
    st.session_state.elapsed = elapsed

    if solved:
        (_, _, photo_count) = solved
        status = "성공"
    else:
        photo_count = 0
        status = "정확한 조합 없음"

    print(
        f"[Cookie Street] 계산 완료 | "
        f"목표금액: {budget:,}원 | "
        f"상품종류: {len(products)}개 | "
        f"사진수: {photo_count}장 | "
        f"최소상품수: {min_items}개 | "
        f"보유제품총액: {inventory_total:,}원 | "
        f"결과: {status} | "
        f"소요시간: {elapsed:.4f}초"
    )

# ============================================================
# 결과
# ============================================================
if st.session_state.result:
    solved, scale, photo_count = st.session_state.result
    (partition_u, patterns) = solved
    elapsed = st.session_state.elapsed or 0

    names = [p[0] for p in products]
    prices = [p[1] for p in products]

    # 최종 검증: 이 검증을 통과하지 않으면 결과를 절대로 출력하지 않는다.
    photo_totals = [
        sum(price * q for price, q in zip(prices, pattern))
        for pattern in patterns
    ]
    photo_items = [sum(pattern) for pattern in patterns]
    grand_total = sum(photo_totals)

    exact_ok = (
        grand_total == budget
        and len(patterns) == photo_count
        and all(items >= min_items for items in photo_items)
    )

    if not exact_ok:
        st.error("계산 결과 검증에 실패했습니다. 잘못된 조합은 표시하지 않습니다.")
        st.stop()

    st.subheader("계산 결과")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("목표금액", f"{budget:,}원")
    c2.metric("최종합계", f"{grand_total:,}원")
    c3.metric("자동 결정 사진 수", f"{photo_count}장")
    c4.metric("계산시간", f"{elapsed:.4f}초")

    st.success(f"✓ 목표금액 {budget:,}원을 정확히 맞췄습니다.")

    cols = st.columns(photo_count)
    aggregate = defaultdict(int)

    for idx, (pattern, photo_total, item_count, col) in enumerate(
        zip(patterns, photo_totals, photo_items, cols), 1
    ):
        with col:
            st.markdown(f"### 📸 사진 {idx}")
            st.caption(f"총 {photo_total:,}원 · {item_count}개")

            for name, price, qty in zip(names, prices, pattern):
                if qty:
                    subtotal = price * qty
                    aggregate[name] += qty
                    st.write(f"**{name}** × {qty} · {subtotal:,}원")

    st.markdown("### 전체 상품 사용 현황")
    usage_rows = []
    for name, price, qty in products:
        usage_rows.append({
            "상품": name,
            "단가": f"{price:,}원",
            "전체 사진 사용수량": aggregate.get(name, 0),
            "보유수량": qty,
            "보유금액": f"{price * qty:,}원",
        })
    st.dataframe(usage_rows, use_container_width=True, hide_index=True)

else:
    # 계산 전 안내
    st.info(
        "사진 수는 자동으로 결정됩니다. 기본적으로 3장을 우선 검토하고, "
        "3장으로 정확한 금액을 만들 수 없으면 다른 사진 수를 탐색합니다."
    )

# ---------------------------------------------------------
# Footer Logo
# ---------------------------------------------------------
# ---------------------------------------------------------
# Footer
# ---------------------------------------------------------
st.markdown(
    '<div style="margin-top: 40px; padding-bottom: 20px; '
    'font-size: 13px; color: #888; text-align: left;">'
    'made by 희란'
    '</div>',
    unsafe_allow_html=True,
)