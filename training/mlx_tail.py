"""Exact target-position evaluation of the frozen Qwen3.5-family final block.

Optional MLX imports occur only when explicitly invoked on Apple Silicon.
Attention consumes the entire sequence; only tokenwise MLP/head work is sliced.
"""
def make_tail(last,norm,head):
    import mlx.nn as nn
    from mlx_lm.models.base import create_attention_mask
    class Tail(nn.Module):
        def __init__(self,last,norm,head):
            super().__init__();self.last=last;self.norm=norm;self.head=head
        def __call__(self,h,prompt_tokens):
            r=self.last.self_attn(self.last.input_layernorm(h),mask=create_attention_mask(h,None))
            h=(h+r)[:,prompt_tokens-1:,:]
            h=h+self.last.mlp(self.last.post_attention_layernorm(h))
            return self.head(self.norm(h))
    if last.is_linear:raise ValueError('A final full-attention block is required')
    tail=Tail(last,norm,head);tail.freeze();tail.eval();return tail


def masked_reference_loss(logits,labels,prompt_tokens):
    import mlx.core as mx
    import mlx.nn as nn
    ce=nn.losses.cross_entropy(logits.astype(mx.float32),labels,reduction='none')
    mask=mx.arange(1,labels.shape[1]+1)>=prompt_tokens
    return mx.sum(ce*mask)/mx.sum(mask)


def tail_loss(model,hidden,labels,prompt_tokens):
    import mlx.core as mx
    import mlx.nn as nn
    return nn.losses.cross_entropy(model(hidden,prompt_tokens).astype(mx.float32),
                                   labels[:,prompt_tokens-1:],reduction='mean')


def restore_mlx_rng(key):
    """MLX 0.32 state is read-only; reconstruct its exact two-uint32 seed."""
    import mlx.core as mx
    values=key.tolist()
    if len(values)!=2 or len(mx.random.state)!=1:
        raise ValueError('Unsupported MLX random-state shape')
    mx.random.seed((int(values[0])<<32)|int(values[1]))
    if not bool(mx.all(mx.random.state[0]==key).item()):
        raise ValueError('MLX RNG restoration differs')
