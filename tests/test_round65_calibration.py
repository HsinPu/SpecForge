from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round65PhoenixAndQueueNoiseCalibrationTests(unittest.TestCase):
    def test_threads_worker_does_not_look_like_bullmq(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tracker" / "compiler").mkdir(parents=True)
            (root / "queue").mkdir()

            (root / "tracker" / "package.json").write_text(
                """
{
  "dependencies": {
    "threads": "^1.7.0"
  }
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "tracker" / "compiler" / "index.js").write_text(
                """
import { spawn, Worker, Pool } from 'threads';

export async function compileAll(variantsToCompile) {
  const workerPool = Pool(() => spawn(new Worker('./worker-thread.js')));
  variantsToCompile.forEach((variant) => {
    workerPool.queue(async (worker) => worker.compileFile(variant));
  });
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "queue" / "package.json").write_text(
                """
{
  "dependencies": {
    "bullmq": "^5.0.0"
  }
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "queue" / "worker.js").write_text(
                """
const { Queue, Worker } = require('bullmq');

new Queue('email-jobs');
new Worker('email-jobs', async (job) => {});
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("bullmq", frameworks)

            bullmq_routes = {
                (route.path, route.method, route.evidence.file)
                for route in facts.api_routes
                if route.framework == "bullmq"
            }
            self.assertIn(("bullmq#email-jobs", "PRODUCE", "queue/worker.js"), bullmq_routes)
            self.assertIn(("bullmq#email-jobs", "CONSUME", "queue/worker.js"), bullmq_routes)
            self.assertFalse(any(route.evidence.file == "tracker/compiler/index.js" for route in facts.api_routes if route.framework == "bullmq"))


if __name__ == "__main__":
    unittest.main()
