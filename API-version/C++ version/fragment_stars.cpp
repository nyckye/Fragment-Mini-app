// Компиляция: g++ -std=c++17 fragment_stars.cpp -lcurl -ljsoncpp -lssl -lcrypto -o fragment_stars
// Установка зависимостей (Ubuntu): sudo apt install libcurl4-openssl-dev libjsoncpp-dev libssl-dev

#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <sstream>
#include <algorithm>
#include <curl/curl.h>
#include <json/json.h>
#include <openssl/bio.h>
#include <openssl/evp.h>
#include <openssl/buffer.h>
#include <regex>

using namespace std;

// КОНФИГУРАЦИЯ
namespace Config {
    const vector<string> MNEMONIC = {
        "penalty", "undo", "fame", "place", "brand", "south", "lunar", "cage",
        "coconut", "girl", "lyrics", "ozone", "fence", "riot", "apology", "diagram",
        "nature", "manage", "there", "brief", "wet", "pole", "debris", "annual"
    };

    const map<string, string> DATA = {
        {"stel_ssid", "ваш_ssid"},
        {"stel_dt", "-240"},
        {"stel_ton_token", "ваш_ton_token"},
        {"stel_token", "ваш_token"}
    };

    const string FRAGMENT_HASH = "ed3ec875a724358cea";
    const string FRAGMENT_PUBLICKEY = "91b296c356bb0894b40397b54565c11f4b29ea610b8e14d2ae1136a50c5d1d03";
    const string FRAGMENT_WALLETS = "te6cckECFgEAArEAAgE0AQsBFP8A9KQT9LzyyAsCAgEgAwYCAUgMBAIBIAgFABm+Xw9qJoQICg65D6AsAQLyBwEeINcLH4IQc2lnbrry4Ip/DQIBIAkTAgFuChIAGa3OdqJoQCDrkOuF/8AAUYAAAAA///+Il7w6CtQZIMze2+aVZS87QjJHoU5yqUljL1aSwzvDrCugAtzQINdJwSCRW49jINcLHyCCEGV4dG69IYIQc2ludL2wkl8D4IIQZXh0brqOtIAg1yEB0HTXIfpAMPpE+Cj6RDBYvZFb4O1E0IEBQdch9AWDB/QOb6ExkTDhgEDXIXB/2zzgMSDXSYECgLmRMOBw4g4NAeaO8O2i7fshgwjXIgKDCNcjIIAg1yHTH9Mf0x/tRNDSANMfINMf0//XCgAK+QFAzPkQmiiUXwrbMeHywIffArNQB7Dy0IRRJbry4IVQNrry4Ib4I7vy0IgikvgA3gGkf8jKAMsfAc8Wye1UIJL4D95w2zzYDgP27aLt+wL0BCFukmwhjkwCIdc5MHCUIccAs44tAdcoIHYeQ2wg10nACPLgkyDXSsAC8uCTINcdBscSwgBSMLDy0InXTNc5MAGk6GwShAe78uCT10rAAPLgk+1V4tIAAcAAkVvg69csCBQgkXCWAdcsCBwS4lIQseMPINdKERAPABCTW9sx4ddM0AByMNcsCCSOLSHy4JLSAO1E0NIAURO68tCPVFAwkTGcAYEBQNch1woA8uCO4sjKAFjPFsntVJPywI3iAJYB+kAB+kT4KPpEMFi68uCR7UTQgQFB1xj0BQSdf8jKAEAEgwf0U/Lgi44UA4MH9Fvy4Iwi1woAIW4Bs7Dy0JDiyFADzxYS9ADJ7VQAGa8d9qJoQBDrkOuFj8ACAUgVFAARsmL7UTQ1woAgABezJftRNBx1yHXCx+B27MAq";
    const string FRAGMENT_ADDRESS = "0:20c429e3bb195f46a582c10eb687c6ed182ec58237a55787f245ec992c337118";
}

// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
namespace Helpers {
    // Callback для curl
    size_t WriteCallback(void* contents, size_t size, size_t nmemb, string* s) {
        size_t newLength = size * nmemb;
        s->append((char*)contents, newLength);
        return newLength;
    }

    // Base64 padding
    string FixBase64Padding(string b64String) {
        int missingPadding = b64String.length() % 4;
        if (missingPadding > 0) {
            b64String.append(4 - missingPadding, '=');
        }
        return b64String;
    }

    // Cookies в строку
    string CookiesToString(const map<string, string>& cookies) {
        stringstream ss;
        bool first = true;
        for (const auto& [key, value] : cookies) {
            if (!first) ss << "; ";
            ss << key << "=" << value;
            first = false;
        }
        return ss.str();
    }

    // URL encode
    string UrlEncode(const string& value) {
        CURL* curl = curl_easy_init();
        char* output = curl_easy_escape(curl, value.c_str(), value.length());
        string result(output);
        curl_free(output);
        curl_easy_cleanup(curl);
        return result;
    }

    // Base64 decode
    string Base64Decode(const string& encoded) {
        BIO *bio, *b64;
        int decodeLen = encoded.length();
        char* buffer = new char[decodeLen];
        
        bio = BIO_new_mem_buf(encoded.c_str(), -1);
        b64 = BIO_new(BIO_f_base64());
        bio = BIO_push(b64, bio);
        
        BIO_set_flags(bio, BIO_FLAGS_BASE64_NO_NL);
        int length = BIO_read(bio, buffer, decodeLen);
        BIO_free_all(bio);
        
        string result(buffer, length);
        delete[] buffer;
        return result;
    }
}

// FRAGMENT CLIENT
class FragmentClient {
private:
    string url;
    map<string, string> cookies;

public:
    FragmentClient(const string& fragmentHash, const map<string, string>& cookiesData)
        : url("https://fragment.com/api?hash=" + fragmentHash), cookies(cookiesData) {}

    string FetchRecipient(const string& query) {
        CURL* curl = curl_easy_init();
        string response;

        if (curl) {
            string postData = "query=" + Helpers::UrlEncode(query) + 
                            "&method=searchStarsRecipient";

            curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
            curl_easy_setopt(curl, CURLOPT_POSTFIELDS, postData.c_str());
            curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, Helpers::WriteCallback);
            curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);

            struct curl_slist* headers = NULL;
            string cookie = "Cookie: " + Helpers::CookiesToString(cookies);
            headers = curl_slist_append(headers, cookie.c_str());
            curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);

            CURLcode res = curl_easy_perform(curl);
            curl_slist_free_all(headers);
            curl_easy_cleanup(curl);

            if (res == CURLE_OK) {
                Json::Value root;
                Json::CharReaderBuilder builder;
                istringstream s(response);
                string errs;
                
                if (Json::parseFromStream(builder, s, &root, &errs)) {
                    cout << "Recipient search: " << response << endl;
                    if (root.isMember("found") && root["found"].isMember("recipient")) {
                        return root["found"]["recipient"].asString();
                    }
                }
            }
        }
        return "";
    }

    string FetchReqId(const string& recipient, int quantity) {
        CURL* curl = curl_easy_init();
        string response;

        if (curl) {
            string postData = "recipient=" + Helpers::UrlEncode(recipient) +
                            "&quantity=" + to_string(quantity) +
                            "&method=initBuyStarsRequest";

            curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
            curl_easy_setopt(curl, CURLOPT_POSTFIELDS, postData.c_str());
            curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, Helpers::WriteCallback);
            curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);

            struct curl_slist* headers = NULL;
            string cookie = "Cookie: " + Helpers::CookiesToString(cookies);
            headers = curl_slist_append(headers, cookie.c_str());
            curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);

            CURLcode res = curl_easy_perform(curl);
            curl_slist_free_all(headers);
            curl_easy_cleanup(curl);

            if (res == CURLE_OK) {
                Json::Value root;
                Json::CharReaderBuilder builder;
                istringstream s(response);
                string errs;
                
                if (Json::parseFromStream(builder, s, &root, &errs)) {
                    cout << "Request ID: " << response << endl;
                    if (root.isMember("req_id")) {
                        return root["req_id"].asString();
                    }
                }
            }
        }
        return "";
    }

    tuple<string, string, string> FetchBuyLink(const string& recipient, 
                                               const string& reqId, 
                                               int quantity) {
        CURL* curl = curl_easy_init();
        string response;

        if (curl) {
            string features = R"(["SendTransaction",{"name":"SendTransaction","maxMessages":255}])";
            
            string postData = 
                "address=" + Helpers::UrlEncode(Config::FRAGMENT_ADDRESS) +
                "&chain=-239" +
                "&walletStateInit=" + Helpers::UrlEncode(Config::FRAGMENT_WALLETS) +
                "&publicKey=" + Helpers::UrlEncode(Config::FRAGMENT_PUBLICKEY) +
                "&features=" + Helpers::UrlEncode(features) +
                "&maxProtocolVersion=2" +
                "&platform=iphone" +
                "&appName=Tonkeeper" +
                "&appVersion=5.0.14" +
                "&transaction=1" +
                "&id=" + Helpers::UrlEncode(reqId) +
                "&show_sender=0" +
                "&method=getBuyStarsLink";

            curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
            curl_easy_setopt(curl, CURLOPT_POSTFIELDS, postData.c_str());
            curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, Helpers::WriteCallback);
            curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);

            struct curl_slist* headers = NULL;
            headers = curl_slist_append(headers, "Accept: application/json");
            headers = curl_slist_append(headers, "Content-Type: application/x-www-form-urlencoded");
            headers = curl_slist_append(headers, "Origin: https://fragment.com");
            string referer = "Referer: https://fragment.com/stars/buy?recipient=" + 
                           recipient + "&quantity=" + to_string(quantity);
            headers = curl_slist_append(headers, referer.c_str());
            string cookie = "Cookie: " + Helpers::CookiesToString(cookies);
            headers = curl_slist_append(headers, cookie.c_str());
            curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);

            CURLcode res = curl_easy_perform(curl);
            curl_slist_free_all(headers);
            curl_easy_cleanup(curl);

            if (res == CURLE_OK) {
                Json::Value root;
                Json::CharReaderBuilder builder;
                istringstream s(response);
                string errs;
                
                if (Json::parseFromStream(builder, s, &root, &errs)) {
                    cout << "Buy link: " << response << endl;
                    
                    if (root.isMember("ok") && root["ok"].asBool() && 
                        root.isMember("transaction")) {
                        auto msg = root["transaction"]["messages"][0];
                        return make_tuple(
                            msg["address"].asString(),
                            msg["amount"].asString(),
                            msg["payload"].asString()
                        );
                    }
                }
            }
        }
        return make_tuple("", "", "");
    }
};

// TON TRANSACTION
class TonTransaction {
private:
    vector<string> mnemonic;

public:
    TonTransaction(const vector<string>& mnemonicWords) : mnemonic(mnemonicWords) {}

    string DecodePayload(const string& payloadBase64, int starsCount) {
        try {
            string fixed = Helpers::FixBase64Padding(payloadBase64);
            string decoded = Helpers::Base64Decode(fixed);
            
            stringstream decodedText;
            for (unsigned char c : decoded) {
                decodedText << (c >= 32 && c < 127 ? (char)c : ' ');
            }
            
            string cleanText = decodedText.str();
            cleanText = regex_replace(cleanText, regex("\\s+"), " ");
            
            regex pattern(to_string(starsCount) + " Telegram Stars.*");
            smatch match;
            if (regex_search(cleanText, match, pattern)) {
                return match.str();
            }
            return cleanText;
        } catch (...) {
            cerr << "Ошибка декодирования payload" << endl;
            return payloadBase64;
        }
    }

    string SendTransaction(const string& recipientAddress, double amountNano,
                          const string& payload, int starsCount) {
        try {
            cout << "\n🔐 Инициализация кошелька..." << endl;
            
            // ПРИМЕЧАНИЕ: Требуется TON C++ SDK (ton-blockchain/ton)
            // Здесь показана структура, нужна реальная имплементация
            
            cout << "✅ Адрес кошелька: [wallet_address]" << endl;
            cout << "\n💸 Отправка транзакции..." << endl;
            cout << "   Получатель: " << recipientAddress << endl;
            cout << "   Сумма: " << amountNano << " TON" << endl;
            cout << "   Комментарий: " << DecodePayload(payload, starsCount) << endl;

            // TODO: Реализация через TON C++ SDK
            
            string mockTxHash = "mock_transaction_hash_" + to_string(time(nullptr));
            cout << "\n✅ Транзакция отправлена успешно!" << endl;
            cout << "📝 Hash: " << mockTxHash << endl;
            
            return mockTxHash;
        } catch (const exception& e) {
            cerr << "\n❌ Ошибка при отправке транзакции: " << e.what() << endl;
            throw;
        }
    }
};

// ОСНОВНАЯ ФУНКЦИЯ
pair<bool, string> BuyStars(const string& username, int starsCount,
                           const string& fragmentHash,
                           const map<string, string>& cookiesData,
                           const vector<string>& mnemonic) {
    FragmentClient fragment(fragmentHash, cookiesData);
    TonTransaction ton(mnemonic);

    cout << "\n" << string(60, '=') << endl;
    cout << "🌟 ПОКУПКА TELEGRAM STARS" << endl;
    cout << string(60, '=') << endl;

    // Шаг 1
    cout << "\n📍 Шаг 1: Поиск получателя " << username << "..." << endl;
    string recipient = fragment.FetchRecipient(username);
    if (recipient.empty()) {
        cout << "❌ Получатель не найден" << endl;
        return {false, ""};
    }
    cout << "✅ Получатель найден: " << recipient << endl;

    // Шаг 2
    cout << "\n📝 Шаг 2: Создание запроса на " << starsCount << " звезд..." << endl;
    string reqId = fragment.FetchReqId(recipient, starsCount);
    if (reqId.empty()) {
        cout << "❌ Не удалось создать запрос" << endl;
        return {false, ""};
    }
    cout << "✅ Request ID: " << reqId << endl;

    // Шаг 3
    cout << "\n🔍 Шаг 3: Получение данных транзакции..." << endl;
    auto [address, amount, payload] = fragment.FetchBuyLink(recipient, reqId, starsCount);
    if (address.empty() || amount.empty() || payload.empty()) {
        cout << "❌ Не удалось получить данные транзакции" << endl;
        return {false, ""};
    }

    double amountTon = stod(amount) / 1'000'000'000;
    cout << "✅ Сумма к оплате: " << fixed << amountTon << " TON" << endl;
    cout << "✅ Адрес Fragment: " << address << endl;

    // Шаг 4
    cout << "\n💳 Шаг 4: Отправка транзакции в блокчейн..." << endl;
    try {
        string txHash = ton.SendTransaction(address, amountTon, payload, starsCount);
        
        if (!txHash.empty()) {
            cout << "\n" << string(60, '=') << endl;
            cout << "🎉 ПОКУПКА ЗАВЕРШЕНА УСПЕШНО!" << endl;
            cout << string(60, '=') << endl;
            return {true, txHash};
        }
    } catch (const exception& e) {
        cout << "\n❌ Ошибка при отправке: " << e.what() << endl;
        return {false, ""};
    }

    return {false, ""};
}

int main() {
    try {
        string username = "@example";
        int starsCount = 100;

        auto [success, txHash] = BuyStars(
            username,
            starsCount,
            Config::FRAGMENT_HASH,
            Config::DATA,
            Config::MNEMONIC
        );

        if (success) {
            cout << "\n🔗 Просмотр транзакции:" << endl;
            cout << "   https://tonviewer.com/transaction/" << txHash << endl;
            cout << "   https://tonscan.org/tx/" << txHash << endl;
        } else {
            cout << "\n❌ Покупка не удалась. Проверьте конфигурацию." << endl;
        }
    } catch (const exception& e) {
        cerr << "\n💥 Критическая ошибка: " << e.what() << endl;
        return 1;
    }

    return 0;
}
