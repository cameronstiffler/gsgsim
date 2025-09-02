def check_sl_loss(gs):
    def has_sl(p):
        for c in getattr(p,"board",[]):
            if str(getattr(c,"rank",None))=="SL" or getattr(c,"rank",None).name=="SL":
                return True
        return False
    p1_alive=has_sl(gs.p1); p2_alive=has_sl(gs.p2)
    if p1_alive and not p2_alive: return gs.p1.name
    if p2_alive and not p1_alive: return gs.p2.name
    if not p1_alive and not p2_alive: return "Draw"
    return None
