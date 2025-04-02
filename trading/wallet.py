# trading/wallet.py
from solana.rpc.api import Client

def load_wallet():
    rpc_client = Client("https://api.mainnet-beta.solana.com")
    # Загрузите кошелек из приватного ключа
    return rpc_client
