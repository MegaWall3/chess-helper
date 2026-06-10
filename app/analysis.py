def is_valid_bestmove(move):
    return (
        len(move) == 4
        and move[0].isalpha()
        and move[1].isdigit()
        and move[2].isalpha()
        and move[3].isdigit()
    )

def parse_engine_info(lines, side):
    info_lines = [line for line in lines if line.startswith('info ') and ' score ' in line]
    if not info_lines:
        return {}

    latest_by_multipv = collect_latest_by_multipv(info_lines)
    latest = latest_by_multipv.get(1, info_lines[-1]).split()
    result = {"raw": info_lines[-1]}
    result["moves"] = parse_candidate_moves(latest_by_multipv)
    result["pvs"] = parse_candidate_pvs(latest_by_multipv)
    result["candidate_scores"] = parse_candidate_scores(latest_by_multipv, side)

    if "depth" in latest:
        result["depth"] = latest[latest.index("depth") + 1]

    if "seldepth" in latest:
        result["seldepth"] = latest[latest.index("seldepth") + 1]

    if "time" in latest:
        result["time_ms"] = latest[latest.index("time") + 1]

    if "nodes" in latest:
        result["nodes"] = latest[latest.index("nodes") + 1]

    if "nps" in latest:
        result["nps"] = latest[latest.index("nps") + 1]

    if "hashfull" in latest:
        result["hashfull"] = latest[latest.index("hashfull") + 1]

    if "score" in latest:
        score_index = latest.index("score")
        score_type = latest[score_index + 1]
        score_value = int(latest[score_index + 2])
        if score_type == "cp":
            result["score_cp"] = score_value
            result["score_text"] = format_score(score_value, side)
        elif score_type == "mate":
            result["mate"] = score_value
            result["mate_text"] = format_mate(score_value, side)

    if "wdl" in latest:
        wdl_index = latest.index("wdl")
        wins = int(latest[wdl_index + 1])
        draws = int(latest[wdl_index + 2])
        losses = int(latest[wdl_index + 3])
        result["wdl"] = (wins, draws, losses)

    if "pv" in latest:
        pv_index = latest.index("pv")
        result["pv"] = " ".join(latest[pv_index + 1:pv_index + 6])

    return result

def collect_latest_by_multipv(info_lines):
    latest_by_multipv = {}
    for line in info_lines:
        parts = line.split()
        multipv = 1
        if "multipv" in parts:
            multipv = int(parts[parts.index("multipv") + 1])
        latest_by_multipv[multipv] = line
    return latest_by_multipv

def parse_candidate_moves(latest_by_multipv):
    return [pv[0] for pv in parse_candidate_pvs(latest_by_multipv) if pv]

def parse_candidate_pvs(latest_by_multipv):
    pvs = []
    for multipv in sorted(latest_by_multipv):
        parts = latest_by_multipv[multipv].split()
        if "pv" not in parts:
            continue

        pv_moves = [
            move for move in parts[parts.index("pv") + 1:]
            if is_valid_bestmove(move)
        ]
        if pv_moves:
            pvs.append(pv_moves)
    return pvs

def parse_candidate_scores(latest_by_multipv, side):
    scores = []
    for multipv in sorted(latest_by_multipv):
        parts = latest_by_multipv[multipv].split()
        if "score" not in parts:
            scores.append({})
            continue

        score_index = parts.index("score")
        score_type = parts[score_index + 1]
        score_value = int(parts[score_index + 2])
        if score_type == "cp":
            scores.append({
                "score_cp": score_value,
                "score_text": format_score(score_value, side),
            })
        elif score_type == "mate":
            scores.append({
                "mate": score_value,
                "mate_text": format_mate(score_value, side),
            })
        else:
            scores.append({})
    return scores

def format_score(score_cp, side):
    if score_cp == 0:
        return "局面均势"

    lead_is_red = score_cp > 0 if side else score_cp < 0
    lead_side = "红方" if lead_is_red else "黑方"
    return f"{lead_side}领先{abs(score_cp)}分"

def format_mate(mate, side):
    lead_is_red = mate > 0 if side else mate < 0
    lead_side = "红方" if lead_is_red else "黑方"
    return f"{lead_side}{abs(mate)}步杀"

def format_wdl(wdl):
    if not wdl:
        return ""

    wins, draws, losses = wdl
    total = wins + draws + losses
    if total == 0:
        return ""

    return f"胜/平/负 {wins / total * 100:.1f}%/{draws / total * 100:.1f}%/{losses / total * 100:.1f}%"

def format_search_fields_cn(engine_analysis):
    if not engine_analysis:
        return "无搜索信息"

    fields = []
    if "depth" in engine_analysis:
        depth_text = f"深度={engine_analysis['depth']}"
        if "seldepth" in engine_analysis:
            depth_text += f"({engine_analysis['seldepth']})"
        fields.append(depth_text)
    if "time_ms" in engine_analysis:
        fields.append(f"用时={engine_analysis['time_ms']}毫秒")
    if "nodes" in engine_analysis:
        nodes_text = f"节点={format_compact_number(engine_analysis['nodes'])}"
        if "nps" in engine_analysis:
            nodes_text += f"({format_compact_number(engine_analysis['nps'])}/秒)"
        fields.append(nodes_text)
    if "hashfull" in engine_analysis:
        fields.append(f"哈希占用={format_hashfull(engine_analysis['hashfull'])}")
    return " ".join(fields) if fields else "无搜索信息"

def format_hashfull(hashfull):
    try:
        return f"{int(hashfull) / 10:.1f}%"
    except (TypeError, ValueError):
        return str(hashfull)

def format_compact_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)

    for suffix, factor in (("B", 1_000_000_000), ("M", 1_000_000), ("K", 1_000)):
        if abs(number) >= factor:
            return f"{number / factor:.1f}{suffix}"
    return str(int(number))
