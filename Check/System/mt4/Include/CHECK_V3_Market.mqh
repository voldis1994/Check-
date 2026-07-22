// CHECK SYSTEM v3 market and status exporters.
#ifndef CHECK_V3_MARKET_MQH
#define CHECK_V3_MARKET_MQH

#include "CHECK_V3_Protocol.mqh"
#include "CHECK_V3_Bridge.mqh"

int CHECK_V3_MARKET_SEQUENCE = 0;
int CHECK_V3_STATUS_SEQUENCE = 0;

string CheckV3StableName(string suffix)
{
   return IntegerToString(AccountNumber()) + "_" + Symbol() + "_" + suffix + ".json";
}

string CheckV3BarJson(int shift)
{
   return "{" +
          "\"time\":" + CheckV3JsonString(CheckV3TimeIso(iTime(Symbol(), PERIOD_M1, shift))) + "," +
          "\"timeframe\":\"M1\"," +
          "\"open\":" + CheckV3JsonNumber(iOpen(Symbol(), PERIOD_M1, shift), Digits) + "," +
          "\"high\":" + CheckV3JsonNumber(iHigh(Symbol(), PERIOD_M1, shift), Digits) + "," +
          "\"low\":" + CheckV3JsonNumber(iLow(Symbol(), PERIOD_M1, shift), Digits) + "," +
          "\"close\":" + CheckV3JsonNumber(iClose(Symbol(), PERIOD_M1, shift), Digits) + "," +
          "\"tick_volume\":" + IntegerToString((int)iVolume(Symbol(), PERIOD_M1, shift)) + "," +
          "\"closed\":true" +
          "}";
}

string CheckV3BarsM1Json()
{
   int total = iBars(Symbol(), PERIOD_M1);
   int count = MathMin(3000, MathMax(0, total - 1));
   string json = "[";
   for(int shift = count; shift >= 1; shift--)
   {
      if(shift != count)
         json += ",";
      json += CheckV3BarJson(shift);
   }
   json += "]";
   return json;
}

bool CheckV3MarketOpen()
{
   return IsConnected() && MarketInfo(Symbol(), MODE_TRADEALLOWED) > 0.0;
}

bool CheckV3ExportMarket(int magicNumber)
{
   RefreshRates();
   CHECK_V3_MARKET_SEQUENCE++;

   int spread = (int)MarketInfo(Symbol(), MODE_SPREAD);
   string json = "{" +
      "\"protocol_version\":" + CheckV3JsonString(CHECK_V3_PROTOCOL_VERSION) + "," +
      "\"message_type\":" + CheckV3JsonString(CHECK_V3_MESSAGE_MARKET) + "," +
      "\"message_id\":" + CheckV3JsonString(CheckV3MessageId(CHECK_V3_MESSAGE_MARKET, CHECK_V3_MARKET_SEQUENCE)) + "," +
      "\"generated_at_utc\":" + CheckV3JsonString(CheckV3UtcIso()) + "," +
      "\"sequence\":" + IntegerToString(CHECK_V3_MARKET_SEQUENCE) + "," +
      "\"account_number\":" + IntegerToString(AccountNumber()) + "," +
      "\"server\":" + CheckV3JsonString(AccountServer()) + "," +
      "\"symbol\":" + CheckV3JsonString(Symbol()) + "," +
      "\"digits\":" + IntegerToString(Digits) + "," +
      "\"point\":" + CheckV3JsonNumber(Point, Digits + 2) + "," +
      "\"tick_size\":" + CheckV3JsonNumber(MarketInfo(Symbol(), MODE_TICKSIZE), Digits + 2) + "," +
      "\"tick_value\":" + CheckV3JsonNumber(MarketInfo(Symbol(), MODE_TICKVALUE), 8) + "," +
      "\"bid\":" + CheckV3JsonNumber(Bid, Digits) + "," +
      "\"ask\":" + CheckV3JsonNumber(Ask, Digits) + "," +
      "\"spread\":" + IntegerToString(spread) + "," +
      "\"stop_level\":" + IntegerToString((int)MarketInfo(Symbol(), MODE_STOPLEVEL)) + "," +
      "\"freeze_level\":" + IntegerToString((int)MarketInfo(Symbol(), MODE_FREEZELEVEL)) + "," +
      "\"min_lot\":" + CheckV3JsonNumber(MarketInfo(Symbol(), MODE_MINLOT), 2) + "," +
      "\"max_lot\":" + CheckV3JsonNumber(MarketInfo(Symbol(), MODE_MAXLOT), 2) + "," +
      "\"lot_step\":" + CheckV3JsonNumber(MarketInfo(Symbol(), MODE_LOTSTEP), 2) + "," +
      "\"magic_number\":" + IntegerToString(magicNumber) + "," +
      "\"bars_m1\":" + CheckV3BarsM1Json() + "," +
      "\"market_open\":" + CheckV3JsonBool(CheckV3MarketOpen()) +
      "}";

   string accountFile = CheckV3PathJoin(CHECK_V3_MARKET_DIR, CheckV3StableName("market"));
   string latestFile = CheckV3PathJoin(CHECK_V3_MARKET_DIR, "latest.json");
   bool ok = CheckV3WriteTextAtomic(accountFile, json);
   ok = CheckV3WriteTextAtomic(latestFile, json) && ok;
   return ok;
}

string CheckV3PositionJson(int index, int magicNumber)
{
   if(!OrderSelect(index, SELECT_BY_POS, MODE_TRADES))
      return "";

   int type = OrderType();
   if(type != OP_BUY && type != OP_SELL)
      return "";

   string side = type == OP_BUY ? "LONG" : "SHORT";
   bool owned = OrderMagicNumber() == magicNumber;
   return "{" +
      "\"position_id\":" + CheckV3JsonString(IntegerToString(OrderTicket())) + "," +
      "\"ticket\":" + IntegerToString(OrderTicket()) + "," +
      "\"symbol\":" + CheckV3JsonString(OrderSymbol()) + "," +
      "\"side\":" + CheckV3JsonString(side) + "," +
      "\"lot\":" + CheckV3JsonNumber(OrderLots(), 2) + "," +
      "\"lots\":" + CheckV3JsonNumber(OrderLots(), 2) + "," +
      "\"entry_price\":" + CheckV3JsonNumber(OrderOpenPrice(), Digits) + "," +
      "\"open_price\":" + CheckV3JsonNumber(OrderOpenPrice(), Digits) + "," +
      "\"stop_loss\":" + CheckV3JsonNumber(OrderStopLoss(), Digits) + "," +
      "\"take_profit\":" + CheckV3JsonNumber(OrderTakeProfit(), Digits) + "," +
      "\"open_time\":" + CheckV3JsonString(CheckV3TimeIso(OrderOpenTime())) + "," +
      "\"current_price\":" + CheckV3JsonNumber(type == OP_BUY ? Bid : Ask, Digits) + "," +
      "\"profit\":" + CheckV3JsonNumber(OrderProfit() + OrderSwap() + OrderCommission(), 2) + "," +
      "\"magic_number\":" + IntegerToString(OrderMagicNumber()) + "," +
      "\"owned_by_ea\":" + CheckV3JsonBool(owned) +
      "}";
}

string CheckV3PositionsJson(int magicNumber)
{
   string json = "[";
   bool first = true;
   for(int i = 0; i < OrdersTotal(); i++)
   {
      string row = CheckV3PositionJson(i, magicNumber);
      if(row == "")
         continue;

      if(!first)
         json += ",";
      json += row;
      first = false;
   }
   json += "]";
   return json;
}

bool CheckV3ExportStatus(int magicNumber)
{
   RefreshRates();
   CHECK_V3_STATUS_SEQUENCE++;

   string json = "{" +
      "\"protocol_version\":" + CheckV3JsonString(CHECK_V3_PROTOCOL_VERSION) + "," +
      "\"message_type\":" + CheckV3JsonString(CHECK_V3_MESSAGE_STATUS) + "," +
      "\"message_id\":" + CheckV3JsonString(CheckV3MessageId(CHECK_V3_MESSAGE_STATUS, CHECK_V3_STATUS_SEQUENCE)) + "," +
      "\"generated_at_utc\":" + CheckV3JsonString(CheckV3UtcIso()) + "," +
      "\"sequence\":" + IntegerToString(CHECK_V3_STATUS_SEQUENCE) + "," +
      "\"account_number\":" + IntegerToString(AccountNumber()) + "," +
      "\"account_id\":" + CheckV3JsonString(IntegerToString(AccountNumber())) + "," +
      "\"server\":" + CheckV3JsonString(AccountServer()) + "," +
      "\"company\":" + CheckV3JsonString(AccountCompany()) + "," +
      "\"name\":" + CheckV3JsonString(AccountName()) + "," +
      "\"currency\":" + CheckV3JsonString(AccountCurrency()) + "," +
      "\"balance\":" + CheckV3JsonNumber(AccountBalance(), 2) + "," +
      "\"equity\":" + CheckV3JsonNumber(AccountEquity(), 2) + "," +
      "\"margin\":" + CheckV3JsonNumber(AccountMargin(), 2) + "," +
      "\"free_margin\":" + CheckV3JsonNumber(AccountFreeMargin(), 2) + "," +
      "\"margin_free\":" + CheckV3JsonNumber(AccountFreeMargin(), 2) + "," +
      "\"connected\":" + CheckV3JsonBool(IsConnected()) + "," +
      "\"trading_allowed\":" + CheckV3JsonBool(IsTradeAllowed()) + "," +
      "\"dlls_allowed\":" + CheckV3JsonBool(IsDllsAllowed()) + "," +
      "\"expert_enabled\":" + CheckV3JsonBool(IsExpertEnabled()) + "," +
      "\"magic_number\":" + IntegerToString(magicNumber) + "," +
      "\"positions\":" + CheckV3PositionsJson(magicNumber) +
      "}";

   string accountFile = CheckV3PathJoin(CHECK_V3_STATUS_DIR, CheckV3StableName("status"));
   string latestFile = CheckV3PathJoin(CHECK_V3_STATUS_DIR, "latest.json");
   bool ok = CheckV3WriteTextAtomic(accountFile, json);
   ok = CheckV3WriteTextAtomic(latestFile, json) && ok;
   return ok;
}

#endif
