"""Numerical optimization and resume checks on a tiny actual Qwen decoder.

Random software fixtures are not historical cases or domain/model performance.
"""
import importlib.util
from pathlib import Path
import tempfile
import unittest

MLX=importlib.util.find_spec('mlx') is not None

@unittest.skipUnless(MLX,'Optional Apple Silicon runtime')
class TailMathTests(unittest.TestCase):
    def test_same_qwen_block_target_loss_and_gradients(self):
        import mlx.core as mx
        import mlx.nn as nn
        from mlx.utils import tree_flatten
        from mlx_lm.models.qwen3_5 import TextModel,TextModelArgs
        from mlx_lm.tuner.lora import LoRALinear
        path=Path(__file__).resolve().parents[1]/'training/mlx_tail.py'
        spec=importlib.util.spec_from_file_location('tail_math',path);math=importlib.util.module_from_spec(spec);spec.loader.exec_module(math)
        mx.random.seed(7)
        args=TextModelArgs(hidden_size=16,intermediate_size=32,num_hidden_layers=1,num_attention_heads=2,
                           num_key_value_heads=1,head_dim=8,vocab_size=32,full_attention_interval=1,
                           rope_parameters={'type':'default','rope_theta':10000.,'partial_rotary_factor':1.})
        model=TextModel(args);model.eval();model.freeze();last=model.layers[-1]
        tail=math.make_tail(last,model.model.norm,model.lm_head)
        last.self_attn.update_modules({k:LoRALinear.from_base(getattr(last.self_attn,k),r=2,scale=2,dropout=0) for k in ('q_proj','v_proj')})
        for key in ('q_proj','v_proj'):
            layer=getattr(last.self_attn,key);layer.lora_b=mx.random.normal(layer.lora_b.shape)*.1
        ids=mx.array([[2,3,4,8,7,6,9,4,5,1,2,6]]);labels=mx.array([[3,4,8,7,6,9,4,5,1,2,6,0]])
        hidden=model.model.embed_tokens(ids)
        value,grad=nn.value_and_grad(model,lambda m:math.masked_reference_loss(m(ids),labels,7))(model)
        cached,cgrad=nn.value_and_grad(tail,math.tail_loss)(tail,hidden,labels,7)
        mx.eval(value,grad,cached,cgrad)
        self.assertAlmostEqual(float(value.item()),float(cached.item()),places=5)
        full=dict(tree_flatten(grad));short=dict(tree_flatten(cgrad))
        for key,g in short.items():
            other=full[key.replace('last.','model.layers.0.',1)]
            self.assertLess(float(mx.max(mx.abs(g-other)).item()),1e-5)
        # A changed prefix must influence later attention: selection is not input truncation.
        changed=model.model.embed_tokens(mx.array([[10,3,4,8,7,6,9,4,5,1,2,6]]))
        self.assertGreater(abs(float(math.tail_loss(tail,changed,labels,7).item())-float(cached.item())),1e-7)
    def test_adamw_rng_restore_continues_identically(self):
        import mlx.core as mx
        import mlx.nn as nn
        import mlx.optimizers as optim
        from mlx.utils import tree_flatten,tree_unflatten
        path=Path(__file__).resolve().parents[1]/'training/mlx_tail.py'
        spec=importlib.util.spec_from_file_location('tail_rng',path);math=importlib.util.module_from_spec(spec);spec.loader.exec_module(math)
        mx.random.seed(17);layer=nn.Linear(4,3);opt=optim.AdamW(learning_rate=.01)
        x=mx.ones((2,4));y=mx.zeros((2,3))
        vg=nn.value_and_grad(layer,lambda m:mx.mean((m(x)-y)**2))
        def step():
            loss,grad=vg(layer);opt.update(layer,grad);mx.eval(loss,layer.parameters(),opt.state);return float(loss.item())
        step()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);mx.save_safetensors(str(root/'weights.safetensors'),dict(tree_flatten(layer.parameters())))
            mx.savez(str(root/'optimizer.npz'),**dict(tree_flatten(opt.state)));mx.savez(str(root/'rng.npz'),key=mx.random.state[0])
            expected_loss=step();expected={k:mx.array(v) for k,v in tree_flatten(layer.parameters())};expected_rng=mx.random.uniform(shape=(5,));mx.eval(expected,expected_rng)
            layer.load_weights(str(root/'weights.safetensors'));opt.state=tree_unflatten(list(mx.load(str(root/'optimizer.npz')).items()))
            math.restore_mlx_rng(mx.load(str(root/'rng.npz'))['key']);actual_loss=step()
            self.assertTrue(bool(mx.all(mx.random.uniform(shape=(5,))==expected_rng).item()))
            self.assertEqual(expected_loss,actual_loss)
            for key,value in tree_flatten(layer.parameters()):self.assertTrue(bool(mx.all(value==expected[key]).item()))

if __name__=='__main__':unittest.main()
