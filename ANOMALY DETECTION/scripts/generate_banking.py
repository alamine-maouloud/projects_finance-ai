import argparse, os
from lamine.domains.banking import simulate_banking

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=str, default="data/banking.csv")
    args = ap.parse_args()

    df = simulate_banking(n=args.n, seed=args.seed)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"Wrote {args.out} shape={df.shape}")

if __name__ == "__main__":
    main()
