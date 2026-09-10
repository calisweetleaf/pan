import unittest
import os
import sys
from zipfile import Path
from PAN_SDK.PAN_SDK import SovereignIdentity, ModelManifest
CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

class ModelManifestVerificationTests(unittest.TestCase):
    def setUp(self):
        self.distributor_identity = SovereignIdentity("Distributor")
        self.model_identity = SovereignIdentity("Model")
        self.manifest = ModelManifest(
            model_name="gemma3-4b-it.lacka",
            model_hash="abc123deadbeef",
            model_public_key_pem=self.model_identity.get_public_key_pem(),
            creator_identity=self.distributor_identity,
        )

    def test_manifest_verification_success(self):
        manifest_dict = self.manifest.to_dict()
        rehydrated_manifest = ModelManifest.from_dict(manifest_dict)

        is_valid = rehydrated_manifest.verify_manifest(
            self.distributor_identity.get_public_key_pem(),
            expected_creator_identity_hash=self.distributor_identity.identity_hash,
        )

        self.assertTrue(is_valid)

    def test_manifest_verification_fails_on_tamper(self):
        rehydrated_manifest = ModelManifest.from_dict(self.manifest.to_dict())
        rehydrated_manifest.content["model_hash"] = "tampered"

        is_valid = rehydrated_manifest.verify_manifest(
            self.distributor_identity.get_public_key_pem(),
            expected_creator_identity_hash=self.distributor_identity.identity_hash,
        )

        self.assertFalse(is_valid)

    def test_manifest_verification_fails_with_wrong_key(self):
        rehydrated_manifest = ModelManifest.from_dict(self.manifest.to_dict())
        intruder_identity = SovereignIdentity("Intruder")

        is_valid = rehydrated_manifest.verify_manifest(intruder_identity.get_public_key_pem())

        self.assertFalse(is_valid)


if __name__ == "__main__":
    unittest.main()
