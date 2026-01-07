import pandas as pd

if __name__ == "__main__":
    df = pd.read_excel("/home/mpc/eicat-ai/api/eval-data/gisd.xlsx")
    print(df.head())
