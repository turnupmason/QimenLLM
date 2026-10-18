"""Optional gateway controls without requiring MLX or downloading model weights."""
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType,SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from qimenllm.models.mlx_gateway import MLXResearchGateway
from qimenllm.contracts import ModelUnavailable

class GatewayOptionsTests(unittest.TestCase):
    def runtime(self):
        core=ModuleType('mlx.core');core.random=SimpleNamespace(seed=Mock())
        core.clear_cache=Mock();core.reset_peak_memory=Mock();core.get_peak_memory=Mock(return_value=123)
        mlx=ModuleType('mlx');mlx.core=core
        tok=SimpleNamespace(apply_chat_template=Mock(return_value='prompt'),encode=Mock(return_value=[1,2]))
        lm=ModuleType('mlx_lm');lm.load=Mock(return_value=(object(),tok))
        output=json.dumps({'answers':{},'evidence':[],'fact_claims':[]})
        lm.stream_generate=Mock(return_value=iter([SimpleNamespace(text=output,generation_tokens=5,generation_tps=2.,finish_reason='stop')]))
        sample=ModuleType('mlx_lm.sample_utils');sample.make_sampler=Mock(return_value='sampler')
        return {'mlx':mlx,'mlx.core':core,'mlx_lm':lm,'mlx_lm.sample_utils':sample},tok,lm
    def test_disable_thinking_is_explicit_and_local_adapter_is_passed(self):
        modules,tok,lm=self.runtime()
        with tempfile.TemporaryDirectory() as tmp,patch.dict(sys.modules,modules):
            root=Path(tmp);adapter=root/'adapter';adapter.mkdir()
            for name in ('adapters.safetensors','adapter_config.json'):(adapter/name).write_bytes(b'fixture')
            gateway=MLXResearchGateway(root,revision='pinned',enable_thinking=False,adapter_path=adapter)
            _,telemetry=gateway.generate_research({'known_information':[]})
            self.assertIs(tok.apply_chat_template.call_args.kwargs['enable_thinking'],False)
            self.assertEqual(lm.load.call_args.kwargs['adapter_path'],str(adapter))
            self.assertIs(lm.load.call_args.kwargs['trust_remote_code'],False)
            self.assertIs(telemetry['enable_thinking'],False)
    def test_old_default_preserves_template_options(self):
        modules,tok,lm=self.runtime()
        with tempfile.TemporaryDirectory() as tmp,patch.dict(sys.modules,modules):
            gateway=MLXResearchGateway(tmp,revision='pinned');gateway.generate_research({})
            self.assertNotIn('enable_thinking',tok.apply_chat_template.call_args.kwargs)
            self.assertNotIn('adapter_path',lm.load.call_args.kwargs)
    def test_missing_adapter_cannot_fall_back_silently_to_base(self):
        modules,tok,lm=self.runtime()
        with tempfile.TemporaryDirectory() as tmp,patch.dict(sys.modules,modules):
            with self.assertRaises(ModelUnavailable):MLXResearchGateway(tmp,revision='pinned',adapter_path=Path(tmp)/'missing')
            lm.load.assert_not_called()

if __name__=='__main__':unittest.main()
