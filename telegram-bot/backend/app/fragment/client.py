import httpx
import logging
from typing import Optional, Tuple, Dict

logger = logging.getLogger(__name__)


def get_cookies(fragment_data: dict) -> dict:

    return {
        'stel_ssid': fragment_data.get('stel_ssid', ''),
        'stel_dt': fragment_data.get('stel_dt', ''),
        'stel_ton_token': fragment_data.get('stel_ton_token', ''),
        'stel_token': fragment_data.get('stel_token', ''),
    }


class FragmentClient:

    
    def __init__(self, fragment_hash: str, fragment_data: dict, 
                 fragment_address: str, fragment_publickey: str, 
                 fragment_wallets: str):
        self.url = f"https://fragment.com/api?hash={fragment_hash}"
        self.fragment_data = fragment_data
        self.fragment_address = fragment_address
        self.fragment_publickey = fragment_publickey
        self.fragment_wallets = fragment_wallets
    
    async def fetch_recipient(self, query: str) -> Optional[str]:

        query = query.lstrip('@')
        data = {"query": query, "method": "searchStarsRecipient"}
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.url, 
                    cookies=get_cookies(self.fragment_data), 
                    data=data
                )
                
                logger.info(f"Fragment API response for {query}: {response.status_code}")
                
                if response.status_code != 200:
                    logger.error(f"Fragment API error: {response.status_code}")
                    return None
                
                result = response.json()
                logger.debug(f"Fragment response: {result}")
                
                recipient = result.get("found", {}).get("recipient")
                
                if recipient:
                    logger.info(f"✅ User found: {recipient}")
                else:
                    logger.warning(f"❌ User not found: {query}")
                
                return recipient
                
        except Exception as e:
            logger.error(f"Error checking user {query}: {e}")
            return None
    
    async def fetch_user_profile(self, query: str) -> Optional[Dict]:

        query = query.lstrip('@')
        data = {"query": query, "method": "searchStarsRecipient"}
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.url, 
                    cookies=get_cookies(self.fragment_data), 
                    data=data
                )
                
                if response.status_code != 200:
                    logger.error(f"Fragment API error: {response.status_code}")
                    return None
                
                result = response.json()
                logger.info(f"📥 Full Fragment API response: {result}")
                
                found = result.get("found", {})
                logger.info(f"📦 Found data: {found}")
                
                if not found:
                    logger.warning(f"❌ No 'found' data for {query}")
                    return None
                
                # Извлекаем photo_url из HTML тега
                photo_html = found.get("photo", "")
                photo_url = None
                if photo_html and 'src="' in photo_html:
                    # Парсим: <img src="URL" />
                    start = photo_html.find('src="') + 5
                    end = photo_html.find('"', start)
                    if start > 4 and end > start:
                        photo_url = photo_html[start:end]
                        logger.info(f"📸 Extracted photo URL: {photo_url}")
                
                # Парсим данные
                user_profile = {
                    "username": query,  # Оригинальный username
                    "recipient": found.get("recipient"),  # Токен для транзакций
                    "user_id": found.get("user_id") or found.get("id"),
                    "first_name": found.get("name") or found.get("first_name") or found.get("firstName"),
                    "last_name": found.get("last_name") or found.get("lastName"),
                    "photo_url": photo_url,
                    "is_premium": found.get("is_premium") or found.get("isPremium", False)
                }
                
                logger.info(f"✅ Profile parsed for {query}: {user_profile}")
                return user_profile
                
        except Exception as e:
            logger.error(f"Error fetching profile for {query}: {e}")
            return None
            return None
    
    async def fetch_req_id(self, recipient: str, quantity: int) -> Optional[str]:

        data = {
            "recipient": recipient, 
            "quantity": quantity, 
            "method": "initBuyStarsRequest"
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.url, 
                    cookies=get_cookies(self.fragment_data), 
                    data=data
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to get req_id: {response.status_code}")
                    return None
                
                result = response.json()
                req_id = result.get("req_id")
                
                if req_id:
                    logger.info(f"✅ Request ID obtained: {req_id}")
                else:
                    logger.error(f"No req_id in response: {result}")
                
                return req_id
                
        except Exception as e:
            logger.error(f"Error getting req_id: {e}")
            return None
    
    async def fetch_buy_link(self, recipient: str, req_id: str, 
                           quantity: int) -> Tuple[Optional[str], Optional[str], Optional[str]]:

        data = {
            "address": self.fragment_address,
            "chain": "-239",
            "walletStateInit": self.fragment_wallets,
            "publicKey": self.fragment_publickey,
            "features": ["SendTransaction", {"name": "SendTransaction", "maxMessages": 255}],
            "maxProtocolVersion": 2,
            "platform": "iphone",
            "appName": "Tonkeeper",
            "appVersion": "5.0.14",
            "transaction": "1",
            "id": req_id,
            "show_sender": "0",
            "method": "getBuyStarsLink"
        }
        
        headers = {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://fragment.com",
            "referer": f"https://fragment.com/stars/buy?recipient={recipient}&quantity={quantity}",
            "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "x-requested-with": "XMLHttpRequest"
        }
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    self.url, 
                    headers=headers, 
                    cookies=get_cookies(self.fragment_data), 
                    data=data
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to get buy link: {response.status_code}")
                    return None, None, None
                
                json_data = response.json()
                logger.debug(f"Buy link response: {json_data}")
                
                if json_data.get("ok") and "transaction" in json_data:
                    transaction = json_data["transaction"]
                    messages = transaction.get("messages", [])
                    
                    if not messages:
                        logger.error("No messages in transaction")
                        return None, None, None
                    
                    first_message = messages[0]
                    address = first_message.get("address")
                    amount = first_message.get("amount")
                    payload = first_message.get("payload")
                    
                    logger.info(f"✅ Transaction params obtained")
                    return address, amount, payload
                else:
                    logger.error(f"Invalid response: {json_data}")
                    return None, None, None
                    
        except Exception as e:
            logger.error(f"Error getting buy link: {e}")
            return None, None, None
