import subprocess
import sys

def run_sim(ai_side):
    result = subprocess.run([
        sys.executable, "gsg_sim.py", "--ai", ai_side, "--moves", "e,e,e,e"
    ], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return result.stdout

def test_ai_narc_human_pcu():
    output = run_sim("NARC")
    if "AI enabled for: NARC" not in output:
        print("DEBUG OUTPUT:\n", output)
    assert "AI enabled for: NARC" in output
    assert "TURN" in output
    print("test_ai_narc_human_pcu passed")

def test_ai_pcu_human_narc():
    output = run_sim("PCU")
    if "AI enabled for: PCU" not in output:
        print("DEBUG OUTPUT:\n", output)
    assert "AI enabled for: PCU" in output
    assert "TURN" in output
    print("test_ai_pcu_human_narc passed")

if __name__ == "__main__":
    test_ai_narc_human_pcu()
    test_ai_pcu_human_narc()
