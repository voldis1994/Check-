// CHECK SYSTEM v3 command execution.
#ifndef CHECK_V3_EXECUTION_MQH
#define CHECK_V3_EXECUTION_MQH

#include "CHECK_V3_Protocol.mqh"
#include "CHECK_V3_Bridge.mqh"

string CheckV3SafeFilePart(string value)
{
   string out = value;
   StringReplace(out, "\\", "_");
   StringReplace(out, "/", "_");
   StringReplace(out, ":", "_");
   StringReplace(out, "*", "_");
   StringReplace(out, "?", "_");
   StringReplace(out, "\"", "_");
   StringReplace(out, "<", "_");
   StringReplace(out, ">", "_");
   StringReplace(out, "|", "_");
   StringReplace(out, " ", "_");
   if(StringLen(out) == 0)
      out = "unknown";
   return out;
}

string CheckV3BrokerErrorMessage(int errorCode)
{
   switch(errorCode)
   {
      case 0: return "OK";
      case 4: return "Trade server busy";
      case 6: return "No connection";
      case 8: return "Too frequent requests";
      case 64: return "Account disabled";
      case 65: return "Invalid account";
      case 129: return "Invalid price";
      case 130: return "Invalid stops";
      case 131: return "Invalid trade volume";
      case 132: return "Market closed";
      case 133: return "Trade disabled";
      case 134: return "Not enough money";
      case 135: return "Price changed";
      case 136: return "Off quotes";
      case 137: return "Broker busy";
      case 138: return "Requote";
      case 146: return "Trade context busy";
      case 147: return "Expiration denied";
      case 148: return "Too many orders";
      default: return "MT4 broker error " + IntegerToString(errorCode);
   }
}

string CheckV3ProcessedMarkerPath(string commandId)
{
   return CheckV3PathJoin(CHECK_V3_ARCHIVE_DIR, "processed_" + CheckV3SafeFilePart(commandId) + ".json");
}

bool CheckV3CommandProcessed(string commandId)
{
   return CheckV3PathExists(CheckV3ProcessedMarkerPath(commandId));
}

bool CheckV3WriteProcessedMarker(string commandId, string sourceFile)
{
   string json = "{" +
      "\"protocol_version\":" + CheckV3JsonString(CHECK_V3_PROTOCOL_VERSION) + "," +
      "\"message_type\":\"PROCESSED_COMMAND\"," +
      "\"command_id\":" + CheckV3JsonString(commandId) + "," +
      "\"source_file\":" + CheckV3JsonString(sourceFile) + "," +
      "\"processed_at_utc\":" + CheckV3JsonString(CheckV3UtcIso()) +
      "}";
   return CheckV3WriteTextAtomic(CheckV3ProcessedMarkerPath(commandId), json);
}

bool CheckV3ArchiveCommandFile(string sourcePath, string commandId, string prefix)
{
   string target = CheckV3PathJoin(
      CHECK_V3_ARCHIVE_DIR,
      prefix + "_" + CheckV3SafeFilePart(commandId) + "_" + IntegerToString(GetTickCount()) + ".json"
   );
   int flags = CHECK_V3_MOVEFILE_REPLACE_EXISTING |
               CHECK_V3_MOVEFILE_COPY_ALLOWED |
               CHECK_V3_MOVEFILE_WRITE_THROUGH;
   return MoveFileExW(CheckV3NormalizePath(sourcePath), target, flags);
}

bool CheckV3SelectTicket(int ticket)
{
   if(ticket <= 0)
      return false;
   return OrderSelect(ticket, SELECT_BY_TICKET, MODE_TRADES);
}

int CheckV3CommandTicket(string json)
{
   int ticket = (int)CheckV3JsonGetNumber(json, "ticket", 0.0);
   if(ticket > 0)
      return ticket;
   string positionId = CheckV3JsonGetString(json, "position_id", "");
   if(StringLen(positionId) > 0)
      return (int)StrToInteger(positionId);
   return 0;
}

void CheckV3WriteAck(
   string commandId,
   bool success,
   int ticket,
   string action,
   string sourceFile,
   int brokerError,
   double price,
   double stopLoss,
   double takeProfit,
   double lots,
   string message
)
{
   string ticketJson = ticket > 0 ? IntegerToString(ticket) : "null";
   string json = "{" +
      "\"protocol_version\":" + CheckV3JsonString(CHECK_V3_PROTOCOL_VERSION) + "," +
      "\"message_type\":" + CheckV3JsonString(CHECK_V3_MESSAGE_ACK) + "," +
      "\"message_id\":" + CheckV3JsonString(CheckV3MessageId(CHECK_V3_MESSAGE_ACK, GetTickCount())) + "," +
      "\"generated_at_utc\":" + CheckV3JsonString(CheckV3UtcIso()) + "," +
      "\"command_id\":" + CheckV3JsonString(commandId) + "," +
      "\"action\":" + CheckV3JsonString(action) + "," +
      "\"success\":" + CheckV3JsonBool(success) + "," +
      "\"accepted\":" + CheckV3JsonBool(success) + "," +
      "\"reject\":" + CheckV3JsonBool(!success) + "," +
      "\"ticket\":" + ticketJson + "," +
      "\"broker_order_id\":" + (ticket > 0 ? CheckV3JsonString(IntegerToString(ticket)) : "null") + "," +
      "\"broker_error\":" + IntegerToString(brokerError) + "," +
      "\"broker_error_message\":" + CheckV3JsonString(CheckV3BrokerErrorMessage(brokerError)) + "," +
      "\"message\":" + CheckV3JsonString(message) + "," +
      "\"source_file\":" + CheckV3JsonString(sourceFile) + "," +
      "\"applied\":{\"price\":" + CheckV3JsonNumber(price, Digits) +
         ",\"stop_loss\":" + CheckV3JsonNumber(stopLoss, Digits) +
         ",\"take_profit\":" + CheckV3JsonNumber(takeProfit, Digits) +
         ",\"lots\":" + CheckV3JsonNumber(lots, 2) + "}" +
      "}";

   string fileName = "ack_" + CheckV3SafeFilePart(commandId) + "_" + IntegerToString(GetTickCount()) + ".json";
   CheckV3WriteTextAtomic(CheckV3PathJoin(CHECK_V3_ACK_DIR, fileName), json);
}

bool CheckV3ValidateCommand(string json, string commandId, string action, string symbol, string sourceFile)
{
   if(CheckV3JsonGetString(json, "protocol_version", CHECK_V3_PROTOCOL_VERSION) != CHECK_V3_PROTOCOL_VERSION)
   {
      CheckV3WriteAck(commandId, false, 0, action, sourceFile, 0, 0, 0, 0, 0, "protocol_version mismatch");
      return false;
   }
   if(StringLen(symbol) > 0 && symbol != Symbol())
   {
      CheckV3WriteAck(commandId, false, 0, action, sourceFile, 0, 0, 0, 0, 0, "command symbol does not match chart symbol");
      return false;
   }
   return true;
}

void CheckV3ExecuteOpen(string json, string commandId, string sourceFile, int defaultMagic)
{
   string side = CheckV3UpperAscii(CheckV3JsonGetString(json, "side", ""));
   int type = (side == "SHORT" || side == "SELL") ? OP_SELL : OP_BUY;
   double lots = CheckV3JsonGetNumber(json, "lot", CheckV3JsonGetNumber(json, "lots", 0.0));
   int magic = (int)CheckV3JsonGetNumber(json, "magic_number", defaultMagic);
   double stopLoss = CheckV3JsonGetNumber(json, "stop_loss", 0.0);
   double takeProfit = CheckV3JsonGetNumber(json, "take_profit", 0.0);
   int slippage = (int)CheckV3JsonGetNumber(json, "slippage", 20.0);
   string comment = "CHECKv3 " + commandId;

   if(lots <= 0.0)
   {
      CheckV3WriteAck(commandId, false, 0, "OPEN", sourceFile, 131, 0, stopLoss, takeProfit, lots, "lot must be positive");
      return;
   }

   RefreshRates();
   double price = type == OP_BUY ? Ask : Bid;
   ResetLastError();
   int ticket = OrderSend(Symbol(), type, lots, NormalizeDouble(price, Digits), slippage,
                          NormalizeDouble(stopLoss, Digits), NormalizeDouble(takeProfit, Digits),
                          comment, magic, 0, type == OP_BUY ? clrBlue : clrRed);
   int errorCode = GetLastError();
   if(ticket > 0 && OrderSelect(ticket, SELECT_BY_TICKET, MODE_TRADES))
   {
      CheckV3WriteAck(commandId, true, ticket, "OPEN", sourceFile, 0, OrderOpenPrice(),
                      OrderStopLoss(), OrderTakeProfit(), OrderLots(), "order opened");
      return;
   }

   CheckV3WriteAck(commandId, false, ticket, "OPEN", sourceFile, errorCode, price,
                   stopLoss, takeProfit, lots, "OrderSend rejected");
}

void CheckV3ExecuteModify(string json, string commandId, string sourceFile)
{
   int ticket = CheckV3CommandTicket(json);
   if(!CheckV3SelectTicket(ticket))
   {
      CheckV3WriteAck(commandId, false, ticket, "MODIFY", sourceFile, 0, 0, 0, 0, 0, "ticket not found");
      return;
   }

   double stopLoss = CheckV3JsonGetNumber(json, "stop_loss", OrderStopLoss());
   double takeProfit = CheckV3JsonGetNumber(json, "take_profit", OrderTakeProfit());
   ResetLastError();
   bool ok = OrderModify(ticket, OrderOpenPrice(), NormalizeDouble(stopLoss, Digits),
                         NormalizeDouble(takeProfit, Digits), OrderExpiration(), clrNONE);
   int errorCode = GetLastError();
   if(ok && OrderSelect(ticket, SELECT_BY_TICKET, MODE_TRADES))
   {
      CheckV3WriteAck(commandId, true, ticket, "MODIFY", sourceFile, 0, OrderOpenPrice(),
                      OrderStopLoss(), OrderTakeProfit(), OrderLots(), "order modified");
      return;
   }

   CheckV3WriteAck(commandId, false, ticket, "MODIFY", sourceFile, errorCode, OrderOpenPrice(),
                   stopLoss, takeProfit, OrderLots(), "OrderModify rejected");
}

void CheckV3ExecuteClose(string json, string commandId, string sourceFile)
{
   int ticket = CheckV3CommandTicket(json);
   if(!CheckV3SelectTicket(ticket))
   {
      CheckV3WriteAck(commandId, false, ticket, "CLOSE", sourceFile, 0, 0, 0, 0, 0, "ticket not found");
      return;
   }

   double fraction = CheckV3JsonGetNumber(json, "close_fraction", 1.0);
   if(fraction <= 0.0 || fraction > 1.0)
      fraction = 1.0;

   double lots = NormalizeDouble(OrderLots() * fraction, 2);
   if(lots <= 0.0)
      lots = OrderLots();

   int type = OrderType();
   RefreshRates();
   double price = type == OP_BUY ? Bid : Ask;
   int slippage = (int)CheckV3JsonGetNumber(json, "slippage", 20.0);
   ResetLastError();
   bool ok = OrderClose(ticket, lots, NormalizeDouble(price, Digits), slippage, clrYellow);
   int errorCode = GetLastError();
   CheckV3WriteAck(commandId, ok, ticket, "CLOSE", sourceFile, ok ? 0 : errorCode, price,
                   OrderStopLoss(), OrderTakeProfit(), lots, ok ? "order closed" : "OrderClose rejected");
}

void CheckV3ExecuteCommandFile(string commandPath, string sourceFile, int defaultMagic)
{
   string json = CheckV3ReadText(commandPath);
   if(StringLen(json) == 0)
      return;

   string commandId = CheckV3JsonGetString(json, "command_id", "");
   if(StringLen(commandId) == 0)
      commandId = sourceFile;

   if(CheckV3CommandProcessed(commandId))
   {
      CheckV3ArchiveCommandFile(commandPath, commandId, "duplicate");
      return;
   }

   string action = CheckV3UpperAscii(CheckV3JsonGetString(json, "action", ""));
   string symbol = CheckV3JsonGetString(json, "symbol", Symbol());
   if(!CheckV3ValidateCommand(json, commandId, action, symbol, sourceFile))
   {
      CheckV3WriteProcessedMarker(commandId, sourceFile);
      CheckV3ArchiveCommandFile(commandPath, commandId, "rejected");
      return;
   }

   if(action == "OPEN")
      CheckV3ExecuteOpen(json, commandId, sourceFile, defaultMagic);
   else if(action == "MODIFY")
      CheckV3ExecuteModify(json, commandId, sourceFile);
   else if(action == "CLOSE")
      CheckV3ExecuteClose(json, commandId, sourceFile);
   else
      CheckV3WriteAck(commandId, false, 0, action, sourceFile, 0, 0, 0, 0, 0, "unsupported action");

   CheckV3WriteProcessedMarker(commandId, sourceFile);
   CheckV3ArchiveCommandFile(commandPath, commandId, "command");
}

void CheckV3ExecuteCommands(int defaultMagic)
{
   string pattern = CheckV3PathJoin(CHECK_V3_COMMANDS_DIR, "*.json");
   string fileName = "";
   long handle = FileFindFirst(pattern, fileName);
   if(handle == INVALID_HANDLE)
      return;

   do
   {
      if(fileName == "." || fileName == "..")
         continue;
      string commandPath = CheckV3PathJoin(CHECK_V3_COMMANDS_DIR, fileName);
      CheckV3ExecuteCommandFile(commandPath, fileName, defaultMagic);
   }
   while(FileFindNext(handle, fileName));

   FileFindClose(handle);
}

#endif
