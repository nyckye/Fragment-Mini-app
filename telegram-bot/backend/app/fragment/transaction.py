import base64
import re
import logging
from typing import Optional, Tuple
from tonutils.client import TonapiClient
from tonutils.wallet import WalletV5R1

logger = logging.getLogger(__name__)


def fix_base64_padding(b64_string: str) -> str:
    missing_padding = len(b64_string) % 4
    if missing_padding:
        b64_string += '=' * (4 - missing_padding)
    return b64_string


class TonTransaction:
    
    def __init__(self, api_key: str, mnemonic: list):
        self.api_key = api_key
        self.mnemonic = mnemonic
        self.client = None
        self.wallet = None
    
    async def initialize_wallet(self):
      
        try:
            self.client = TonapiClient(
                api_key=self.api_key,
                is_testnet=False
            )
            
            self.wallet, public_key, private_key, mnemonic = WalletV5R1.from_mnemonic(
                self.client, 
                self.mnemonic
            )
            
            logger.info("✅ TON Wallet initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize wallet: {e}")
            return False
    
    def decode_payload(self, encoded_payload: str, stars: int) -> str:
      
        try:
            decoded_bytes = base64.b64decode(fix_base64_padding(encoded_payload))
            decoded_text = ''.join(
                chr(b) if 32 <= b < 127 else ' ' 
                for b in decoded_bytes
            )
            clean_text = re.sub(r'\s+', ' ', decoded_text).strip()
            match = re.search(rf"{stars} Telegram Stars.*", clean_text)
            final_text = match.group(0) if match else clean_text
            
            logger.info(f"Decoded payload: {final_text[:50]}...")
            return final_text
            
        except Exception as e:
            logger.error(f"Error decoding payload: {e}")
            return ""
    
    async def send_ton_transaction(
        self, 
        recipient: str, 
        amount_ton: float, 
        payload: str, 
        stars: int
    ) -> Tuple[bool, Optional[bytes], Optional[str]]:
      
        if not self.wallet:
            initialized = await self.initialize_wallet()
            if not initialized:
                return False, None, "Failed to initialize wallet"
        
        if not recipient:
            logger.error("❌ Recipient address is empty")
            return False, None, "Recipient address is required"
        
        if amount_ton <= 0:
            logger.error("❌ Invalid amount")
            return False, None, "Amount must be greater than 0"
        
        try:
            decoded_payload = self.decode_payload(payload, stars)
            
            logger.info(f"📤 Sending transaction:")
            logger.info(f"   To: {recipient}")
            logger.info(f"   Amount: {amount_ton} TON")
            logger.info(f"   Stars: {stars}")
            
            tx_hash = await self.wallet.transfer(
                destination=recipient,
                amount=amount_ton,
                body=decoded_payload,
            )
            
            logger.info(f"✅ Transaction sent successfully!")
            
            # Проверяем тип tx_hash и конвертируем в bytes если нужно
            if isinstance(tx_hash, str):
                # Если строка, конвертируем hex в bytes
                tx_hash_bytes = bytes.fromhex(tx_hash)
                logger.info(f"   TX Hash: {tx_hash}")
            else:
                # Если уже bytes
                tx_hash_bytes = tx_hash
                logger.info(f"   TX Hash: {tx_hash.hex()}")
            
            return True, tx_hash_bytes, None
            
        except Exception as e:
            error_msg = f"Transaction failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return False, None, error_msg
    
    async def get_balance(self) -> Optional[float]:

        if not self.wallet:
            await self.initialize_wallet()
        
        try:
            # Конвертируем address в строку
            address_str = self.wallet.address.to_str()
            balance_nano = await self.client.get_account_balance(address_str)
            balance_ton = balance_nano / 1_000_000_000
            
            logger.info(f"💰 Wallet balance: {balance_ton:.4f} TON")
            return balance_ton
            
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return None
