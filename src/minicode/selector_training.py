"""Training helpers shared with the executable notebook (ML imports are lazy)."""
from __future__ import annotations

from contextlib import nullcontext
import hashlib
import json
from pathlib import Path

from .selector_protocol import selector_messages, training_record


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def training_dataset(rows):
    from datasets import Dataset
    return Dataset.from_list([training_record(row) for row in rows])


def check_supervision(trainer, expected_labels):
    """Reject missing, truncated or unmasked targets before any optimizer step."""
    if len(trainer.train_dataset) != len(expected_labels):
        raise ValueError('Training dataset length changed')
    tokenizer = trainer.processing_class
    for index, expected in enumerate(expected_labels):
        example = trainer.train_dataset[index]
        batch = trainer.data_collator([example])
        labels = batch['labels'][0]
        mask = labels.ne(-100)
        if not bool(mask.any()) or bool(mask.all()):
            raise ValueError(f'Invalid completion-only supervision at example {index}')
        decoded = tokenizer.decode(labels[mask].tolist(), skip_special_tokens=True).strip()
        if decoded != expected:
            raise ValueError(f'Target lost/truncated at example {index}: {decoded!r}')
    return {'checked': len(expected_labels), 'completion_only': True}


def generate_text(model, tokenizer, messages, max_new_tokens=16):
    import torch
    encoded = tokenizer.apply_chat_template(messages, tokenize=True,
        add_generation_prompt=True, return_tensors='pt', return_dict=True).to(model.device)
    encoded.pop('token_type_ids', None)
    # No silent left truncation: production and local evaluation use the same limit.
    if encoded['input_ids'].shape[1] > 4096:
        raise ValueError('Selector input exceeds 4096 tokens')
    model.eval()
    with torch.inference_mode():
        result = model.generate(**encoded, max_new_tokens=max_new_tokens, do_sample=False,
                                pad_token_id=tokenizer.eos_token_id)
    return tokenizer.decode(result[0, encoded['input_ids'].shape[1]:],
                            skip_special_tokens=True).strip()


def predict(model, tokenizer, rows, *, adapter_enabled=True, include_context=True):
    context = nullcontext() if adapter_enabled else model.disable_adapter()
    with context:
        return [{'id': row['id'], 'tool': (raw := generate_text(model, tokenizer,
                 selector_messages(**row['input'], include_context=include_context))),
                 'raw_output': raw} for row in rows]


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def write_jsonl(path, rows):
    Path(path).write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows),
                          encoding='utf-8')
