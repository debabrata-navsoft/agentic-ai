"""Train the GPT from random initialization on a plain-text file.

    .venv/bin/python -m app.train                       # defaults: ../data/shakespeare.txt, ~0.8M params
    .venv/bin/python -m app.train --steps 200           # quick smoke run

Writes the best checkpoint (lowest validation loss) to checkpoints/model.pt and a CSV loss log.
"""

import argparse
import csv
import math
import time
from pathlib import Path

import torch

from app.model import GPT, CharTokenizer, GPTConfig, save_checkpoint


def get_batch(data: torch.Tensor, block_size: int, batch_size: int) -> tuple[torch.Tensor, torch.Tensor]:
    starts = torch.randint(len(data) - block_size - 1, (batch_size,))
    x = torch.stack([data[i : i + block_size] for i in starts])
    y = torch.stack([data[i + 1 : i + block_size + 1] for i in starts])  # shifted by one: the next char
    return x, y


@torch.no_grad()
def estimate_loss(model: GPT, splits: dict, block_size: int, batch_size: int, iters: int) -> dict:
    model.eval()
    out = {}
    for name, data in splits.items():
        losses = [model(*get_batch(data, block_size, batch_size))[1].item() for _ in range(iters)]
        out[name] = sum(losses) / len(losses)
    model.train()
    return out


def lr_at(step: int, max_steps: int, lr: float, warmup: int) -> float:
    if step < warmup:
        return lr * (step + 1) / warmup
    progress = (step - warmup) / max(1, max_steps - warmup)
    return lr * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * progress)))  # cosine decay to 10%


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", default="../data/shakespeare.txt")
    p.add_argument("--out", default="checkpoints/model.pt")
    p.add_argument("--steps", type=int, default=3000)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--block-size", type=int, default=128)
    p.add_argument("--n-layer", type=int, default=4)
    p.add_argument("--n-head", type=int, default=4)
    p.add_argument("--n-embd", type=int, default=128)
    p.add_argument("--dropout", type=float, default=0.1)
    p.add_argument("--lr", type=float, default=3e-3)
    p.add_argument("--eval-interval", type=int, default=250)
    p.add_argument("--eval-iters", type=int, default=20)
    p.add_argument("--seed", type=int, default=1337)
    args = p.parse_args()

    torch.manual_seed(args.seed)
    text = Path(args.data).read_text(encoding="utf-8")
    tok = CharTokenizer.from_text(text)
    data = torch.tensor(tok.encode(text), dtype=torch.long)
    split = int(0.9 * len(data))
    splits = {"train": data[:split], "val": data[split:]}

    cfg = GPTConfig(
        vocab_size=tok.vocab_size,
        block_size=args.block_size,
        n_layer=args.n_layer,
        n_head=args.n_head,
        n_embd=args.n_embd,
        dropout=args.dropout,
    )
    model = GPT(cfg)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.1)
    print(f"{len(text):,} chars, vocab {tok.vocab_size}, {model.num_params():,} params, {args.steps} steps")
    print(f"random-init loss should be about ln({tok.vocab_size}) = {math.log(tok.vocab_size):.2f}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    log_path = out.with_name("train_log.csv")
    best_val = float("inf")
    start = time.time()

    with log_path.open("w", newline="") as f:
        log = csv.writer(f)
        log.writerow(["step", "train_loss", "val_loss", "lr", "elapsed_s"])
        for step in range(args.steps + 1):
            lr = lr_at(step, args.steps, args.lr, warmup=100)
            if step % args.eval_interval == 0 or step == args.steps:
                losses = estimate_loss(model, splits, args.block_size, args.batch_size, args.eval_iters)
                elapsed = time.time() - start
                log.writerow([step, f"{losses['train']:.4f}", f"{losses['val']:.4f}", f"{lr:.2e}", f"{elapsed:.0f}"])
                f.flush()
                saved = ""
                if losses["val"] < best_val:
                    best_val = losses["val"]
                    save_checkpoint(out, model, tok, step=step, val_loss=best_val, data=str(args.data))
                    saved = "  (saved)"
                print(f"step {step:5d}  train {losses['train']:.4f}  val {losses['val']:.4f}  {elapsed:6.0f}s{saved}")
            if step == args.steps:
                break

            for group in opt.param_groups:
                group["lr"] = lr
            _, loss = model(*get_batch(splits["train"], args.block_size, args.batch_size))
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()

    print(f"done in {time.time() - start:.0f}s, best val loss {best_val:.4f} -> {out}")


if __name__ == "__main__":
    main()
