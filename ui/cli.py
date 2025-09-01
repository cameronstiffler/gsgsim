# ui/cli.py
from __future__ import annotations
from gsg_sim import GameState, Player, Rank, can_target_card, use_ability

class CLI:
    def render_board(self, gs: GameState) -> None:
        def row(p: Player, tag: str):
            print(f"\n== Board ({tag}): {p.name} ==")
            for i, c in enumerate(p.board):
                sts = ",".join(sorted((c.statuses or {}).keys())) or "-"
                print(f"[{i}] {c.name} (rank={c.rank.name}, wind={c.wind}, statuses={sts})")
            if not p.board: print("(empty)")
        row(gs.p1, "P1"); row(gs.p2, "P2")

    def render_hand(self, p: Player, label: str) -> None:
        print(f"\n-- {label} hand ({len(p.hand)} cards) --")
        for i, c in enumerate(p.hand):
            print(f"[{i}] {c.name} (rank={c.rank.name})")
        if not p.hand: print("(empty)")

    def info(self, msg: str) -> None: print(msg)
    def error(self, msg: str) -> None: print(msg)

    # helpers
    def _deploy_from_hand(self, gs: GameState, player: Player, hand_idx: int) -> bool:
        if not (0 <= hand_idx < len(player.hand)):
            self.error("Invalid hand index."); return False
        card = player.hand[hand_idx]
        if card.rank != Rank.SL and not any(c.rank == Rank.SL for c in player.board):
            self.error("Must deploy Squad Leader first."); return False
        player.board.append(card); player.hand.pop(hand_idx)
        self.info(f"Deployed: {card.name}"); return True

    def _use_ability(self, gs: GameState, player: Player, src_idx: int, a_idx: int, tgt_idx: int | None) -> bool:
        enemy = gs.p2 if player is gs.p1 else gs.p1
        if not (0 <= src_idx < len(player.board)): self.error("Invalid source index."); return False
        src = player.board[src_idx]
        try: ability = src.abilities[a_idx]
        except Exception: self.error("Invalid ability index."); return False
        target = None
        if tgt_idx is not None:
            if not (0 <= tgt_idx < len(enemy.board)): self.error("Invalid target index."); return False
            target = enemy.board[tgt_idx]
            if not can_target_card(gs, src, target, player, enemy, ability):
                self.error("Illegal target."); return False
        ok = use_ability(gs, player, src_idx, a_idx, tgt_idx if target is not None else None)
        self.info("Ability resolved." if ok else "Ability failed.")
        return ok

    def run_loop(self, gs: GameState) -> None:
        self.info("\nType 'help' for commands. 'quit' to exit.")
        while True:
            try: line = input("> ").strip()
            except (EOFError, KeyboardInterrupt): print(); break
            if not line: continue
            parts = line.split(); cmd = parts[0].lower()
            if cmd in ("quit", "exit"): break
            if cmd == "help":
                print("Commands:\n  show\n  hand p1|p2\n  deploy p1|p2 HAND_IDX\n  use p1|p2 SRC_IDX ABIL_IDX [TGT_IDX]\n  end\n  quit")
                continue
            if cmd == "show": self.render_board(gs); continue
            if cmd == "hand" and len(parts) >= 2:
                who = gs.p1 if parts[1].lower() == "p1" else gs.p2
                self.render_hand(who, "P1" if who is gs.p1 else "P2"); continue
            if cmd == "deploy" and len(parts) >= 3:
                who = gs.p1 if parts[1].lower() == "p1" else gs.p2
                try: idx = int(parts[2])
                except ValueError: self.error("HAND_IDX must be integer."); continue
                self._deploy_from_hand(gs, who, idx); continue
            if cmd == "use" and len(parts) >= 4:
                who = gs.p1 if parts[1].lower() == "p1" else gs.p2
                try:
                    sidx = int(parts[2]); aidx = int(parts[3])
                    tidx = int(parts[4]) if len(parts) >= 5 else None
                except ValueError: self.error("Indexes must be integers."); continue
                self._use_ability(gs, who, sidx, aidx, tidx); continue
            if cmd == "end":
                self.info("Turn end placeholder."); continue
            self.error("Unknown command. Type 'help'.")