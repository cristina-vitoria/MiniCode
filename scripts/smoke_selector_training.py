#!/usr/bin/env python3
"""Real CPU SFT/LoRA/save/reload smoke; random tiny model, NOT scientific evidence."""
import json
import argparse
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args_cli = parser.parse_args()
    import torch
    from tokenizers import Tokenizer, models, pre_tokenizers
    from transformers import PreTrainedTokenizerFast, Qwen2Config, Qwen2ForCausalLM, set_seed
    from peft import LoraConfig, PeftModel
    from trl import SFTConfig, SFTTrainer
    from minicode.selector_protocol import TOOLS, training_record
    from minicode.specialization_data import load_examples
    from minicode.selector_training import training_dataset, check_supervision, predict
    from minicode.local_selector import LocalSelectorClient
    torch.set_num_threads(2)
    set_seed(42)
    rows = [r for r in load_examples(ROOT/'data/tool_selection/examples.jsonl') if r['split']=='train'][:4]
    vocabulary = {'<unk>': 0, '<pad>': 1, '<eos>': 2, '<system>': 3, '<user>': 4, '<assistant>': 5}
    for word in TOOLS:
        vocabulary[word] = len(vocabulary)
    backend = Tokenizer(models.WordLevel(vocabulary, unk_token='<unk>'))
    backend.pre_tokenizer = pre_tokenizers.WhitespaceSplit()
    tokenizer = PreTrainedTokenizerFast(tokenizer_object=backend, unk_token='<unk>',
        pad_token='<pad>', eos_token='<eos>')
    tokenizer.chat_template = "{% for message in messages %}{{ '<' + message['role'] + '> ' + message['content'] + ' ' }}{% if message['role'] == 'assistant' %}{{ eos_token + ' ' }}{% endif %}{% endfor %}{% if add_generation_prompt %}{{ '<assistant> ' }}{% endif %}"
    config = Qwen2Config(vocab_size=len(tokenizer), hidden_size=32, intermediate_size=64,
        num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2,
        pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id)
    model = Qwen2ForCausalLM(config)
    with tempfile.TemporaryDirectory(prefix='minicode-ml-smoke-') as tmp:
        root = Path(tmp)
        model.save_pretrained(root/'base')
        tokenizer.save_pretrained(root/'base')
        args = SFTConfig(output_dir=str(root/'train'), use_cpu=True, bf16=False, fp16=False,
            max_steps=2, per_device_train_batch_size=1, gradient_accumulation_steps=1,
            max_length=1024, completion_only_loss=True, gradient_checkpointing=False,
            report_to='none', save_strategy='no', logging_steps=1, seed=42)
        trainer = SFTTrainer(model=model, args=args, train_dataset=training_dataset(rows),
            processing_class=tokenizer, peft_config=LoraConfig(r=2, lora_alpha=4,
                target_modules=['q_proj','v_proj'], task_type='CAUSAL_LM'))
        supervision = check_supervision(trainer, [r['label'] for r in rows])
        result = trainer.train()
        trainer.model.eval()
        base = predict(trainer.model, tokenizer, rows[:1], adapter_enabled=False)
        tuned = predict(trainer.model, tokenizer, rows[:1])
        no_context = predict(trainer.model, tokenizer, rows[:1], include_context=False)
        trainer.save_model(str(root/'adapter'))
        restored = PeftModel.from_pretrained(Qwen2ForCausalLM.from_pretrained(root/'base'), root/'adapter')
        assert predict(restored, tokenizer, rows[:1]) == tuned, 'Reload changed prediction'
        direct = LocalSelectorClient(root/'base', adapter=root/'adapter')
        assert direct.complete(training_record(rows[0])['prompt']) == tuned[0]['tool']
        record = training_record(rows[0])
        assert record['completion'][0]['content'] == rows[0]['label']
        report = {'kind':'engineering_smoke_not_model_evaluation', 'passed':True,
            'supervision':supervision, 'steps':result.global_step, 'loss':result.training_loss,
            'conditions_generated':3, 'adapter_reload_identical':True,
            'local_selector_client_identical':True}
        if args_cli.output:
            args_cli.output.parent.mkdir(parents=True,exist_ok=True)
            with args_cli.output.open('x') as stream:
                json.dump(report, stream, indent=2)
                stream.write('\n')
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
