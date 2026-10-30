"""Host-side checks, no board needed:  python -m unittest discover tests
Keeps board/board.json, lib/dragon.py, include/toon_dragon.h and the tester in agreement,
and makes sure every Python file at least compiles."""
import ast, json, pathlib, py_compile, re, sys, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
BOARD = json.loads((ROOT / "board" / "board.json").read_text())


def lib_constants():
    tree = ast.parse((ROOT / "lib" / "dragon.py").read_text())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return out


def header_gpios(name):
    pins = BOARD["headers"][name]["pins"]
    return {int(k): int(re.match(r"IO(\d+)", v).group(1)) for k, v in pins.items() if v.startswith("IO")}


class Repo(unittest.TestCase):
    def test_python_compiles(self):
        for f in ROOT.glob("**/*.py"):
            if ".venv" in f.parts:
                continue
            py_compile.compile(str(f), doraise=True)

    def test_lib_matches_board(self):
        c = lib_constants()
        g = BOARD["gpio"]
        self.assertEqual(c["EYES"], g["eyes"]["gpio"])
        self.assertEqual(c["BOOT"], g["boot_button"]["gpio"])
        self.assertEqual(c["SDA"], g["qwiic_sda"]["gpio"])
        self.assertEqual(c["SCL"], g["qwiic_scl"]["gpio"])
        self.assertEqual({k: v for k, v in c["J3"].items()}, header_gpios("J3"))
        self.assertEqual({k: v for k, v in c["J4"].items() if v is not None}, header_gpios("J4"))
        self.assertEqual(list(c["FREE"]), BOARD["free_gpio"])

    def test_c_header_matches_board(self):
        h = (ROOT / "include" / "toon_dragon.h").read_text()
        j3 = [int(x) for x in re.search(r"DRAGON_J3\[\] = \{([^}]*)\}", h).group(1).split(",")]
        j4 = [int(x) for x in re.search(r"DRAGON_J4\[\] = \{([^}]*)\}", h).group(1).split(",")]
        self.assertEqual(j3, [header_gpios("J3")[i] for i in range(1, 10)])
        self.assertEqual(j4, [header_gpios("J4")[i] for i in range(1, 9)])
        self.assertIn("DRAGON_EYES_PIN     %d " % BOARD["gpio"]["eyes"]["gpio"], h)

    def test_tester_labels_match_board(self):
        sys.path.insert(0, str(ROOT / "tester"))
        src = (ROOT / "tester" / "dragon_tester.py").read_text()
        labels = ast.literal_eval(re.search(r"PIN_LABEL = (\{.*?\})\n", src, re.S).group(1))
        for hdr in ("J3", "J4"):
            for pin, gpio in header_gpios(hdr).items():
                self.assertTrue(labels[gpio].startswith(f"{hdr}.{pin} "), (gpio, labels[gpio]))

    def test_netlist_has_the_pins_we_claim(self):
        nets = BOARD["nets"]
        self.assertIn("U1.22", nets["LED_IO8_STRAP"])     # module pad 22 = IO8 -> eyes
        self.assertIn("D1.4", nets["LED_IO8_STRAP"])
        self.assertIn("U1.23", nets["BOOT_IO9"])
        self.assertIn("J2.3", nets["I2C_SDA_GPIO0"])
        self.assertIn("J2.4", nets["I2C_SCL_GPIO14"])


if __name__ == "__main__":
    unittest.main()
