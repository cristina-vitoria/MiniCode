"""Load an exported adapter directly; no public Colab tunnel is necessary."""
from pathlib import Path

from .selector_training import generate_text, sha256_file


class LocalSelectorClient:
    def __init__(self, model_path, *, device='cpu', quantized=False, revision=None,
                 adapter=None, tokenizer_path=None):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        if device == 'cuda' and not torch.cuda.is_available():
            raise ValueError('CUDA indisponível')
        if quantized and device != 'cuda':
            raise ValueError('QLoRA 4-bit requer CUDA neste protocolo')
        dtype = torch.float32 if device == 'cpu' else torch.float16
        options = dict(revision=revision, dtype=dtype, trust_remote_code=False)
        if quantized:
            options['quantization_config'] = BitsAndBytesConfig(load_in_4bit=True,
                bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=dtype)
            options['device_map'] = {'': 0}
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path or model_path,
            revision=revision if not tokenizer_path else None, trust_remote_code=False)
        self.model_object = AutoModelForCausalLM.from_pretrained(model_path, **options)
        if not quantized:
            self.model_object.to(device)
        if adapter:
            from peft import PeftModel
            self.model_object = PeftModel.from_pretrained(self.model_object, adapter,
                                                        is_trainable=False)
        self.model_object.eval()
        self.model = str(model_path)
        self.metadata = {'model': str(model_path), 'revision': revision, 'device': device,
                         'quantized': quantized, 'adapter': str(adapter) if adapter else None,
                         'adapter_sha256': sha256_file(Path(adapter) / 'adapter_model.safetensors')
                         if adapter else None}

    def complete(self, messages):
        return generate_text(self.model_object, self.tokenizer, messages)
