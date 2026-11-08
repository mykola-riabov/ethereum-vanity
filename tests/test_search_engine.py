import os
import unittest

import ecdsa
from mnemonic import Mnemonic

import secp
from bip32_pure import BIP32, parse_path
from ethereum_address import make_matcher, privkey_to_address, try_match_privkey
from search_engine import Job, SearchEngine

# BIP39 test phrase; the address MetaMask derives from it.
_PHRASE = "abandon " * 11 + "about"
_PATH = "m/44'/60'/0'/0/0"
_ADDR = "0x9858EfFD232B4033E47d90003D41EC34EcaEda94"


def _from_phrase(words: str, path: str) -> bytes:
    return BIP32.from_seed(Mnemonic("english").to_seed(words)).get_privkey_from_path(parse_path(path))


class TestCurve(unittest.TestCase):
    def test_backend_matches_python_ecdsa(self):
        for _ in range(50):
            priv = os.urandom(32)
            raw = ecdsa.SigningKey.from_string(priv, curve=ecdsa.SECP256k1).get_verifying_key().to_string()
            self.assertEqual(secp.pubkey_xy(priv), raw)


class TestDerivation(unittest.TestCase):
    def test_known_phrase(self):
        self.assertEqual(privkey_to_address(_from_phrase(_PHRASE, _PATH)), _ADDR)

    def test_match_returns_checksum_address(self):
        priv = _from_phrase(_PHRASE, _PATH)
        self.assertEqual(try_match_privkey(priv, "0x9858ef", ""), _ADDR)
        self.assertEqual(try_match_privkey(priv, "0x9858Ef", "", case_sensitive=True), _ADDR)
        self.assertIsNone(try_match_privkey(priv, "0x9858EF", "", case_sensitive=True))
        self.assertEqual(try_match_privkey(priv, "9858ef", "", checksum=False), _ADDR.lower())


class TestEngine(unittest.TestCase):
    def test_index_mode_is_recoverable_from_phrase(self):
        job = Job(matcher=make_matcher("0x00", ""), mode="index", path=_PATH, report_every=50)
        with SearchEngine(job, 2) as engine:
            rec = None
            for _ in range(600):
                rec = engine.next_match(timeout=0.1)
                if rec:
                    break
        self.assertIsNotNone(rec)
        self.assertTrue(rec["address"].lower().startswith("0x00"))
        self.assertEqual(privkey_to_address(_from_phrase(rec["mnemonic"], rec["path"])), rec["address"])


if __name__ == "__main__":
    unittest.main()
