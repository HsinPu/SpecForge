from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round135DartFreezedUnionCalibrationTests(unittest.TestCase):
    def test_sealed_freezed_union_classes_with_implements_are_data_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lib = root / "lib" / "rust" / "api"
            lib.mkdir(parents=True)
            (root / "pubspec.yaml").write_text(
                """
name: flutter_fixture
dependencies:
  flutter:
    sdk: flutter
  freezed_annotation: ^2.4.0
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (lib / "http.dart").write_text(
                """
import 'package:freezed_annotation/freezed_annotation.dart';

part 'http.freezed.dart';

class FrbException {}

@freezed
sealed class RsHttpClientError with _$RsHttpClientError implements FrbException {
  const RsHttpClientError._();

  const factory RsHttpClientError.statusCode({
    required int status,
    String? message,
  }) = RsHttpClientError_StatusCode;

  const factory RsHttpClientError.reqwest(
    String field0,
  ) = RsHttpClientError_Reqwest;
}

@freezed
sealed class RTCStatus with _$RTCStatus {
  const factory RTCStatus.connected() = RTCStatus_Connected;
  const factory RTCStatus.error(
    String field0,
  ) = RTCStatus_Error;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            models = {(model.name, model.kind): model for model in facts.data_models}
            error = models[("RsHttpClientError", "dart-freezed-model")]
            self.assertIn("status:int", error.fields)
            self.assertIn("message:String?", error.fields)
            self.assertIn("field0:String", error.fields)
            self.assertIn("factory:statusCode", error.annotations)
            self.assertIn("factory:reqwest", error.annotations)

            status = models[("RTCStatus", "dart-freezed-model")]
            self.assertIn("field0:String", status.fields)
            self.assertIn("factory:connected", status.annotations)
            self.assertIn("factory:error", status.annotations)


if __name__ == "__main__":
    unittest.main()
