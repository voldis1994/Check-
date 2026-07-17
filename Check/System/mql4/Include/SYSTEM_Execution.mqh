#ifndef __SYSTEM_EXECUTION_MQH__
#define __SYSTEM_EXECUTION_MQH__

#property strict

#include <SYSTEM_Control.mqh>
#include <SYSTEM_Status.mqh>

#define SYSTEM_ACK_FILENAME_TEMPLATE "ack_%s_%d.json"
#define SYSTEM_PROCESSED_CMD_FILENAME_TEMPLATE "processed_cmd_%s_%d.txt"
#define SYSTEM_ACK_STATUS_SUCCESS "SUCCESS"
#define SYSTEM_ACK_STATUS_FAILED "FAILED"
#define SYSTEM_ACK_STATUS_REJECTED "REJECTED"
#define SYSTEM_SIDE_BUY "BUY"
#define SYSTEM_SIDE_SELL "SELL"
#define SYSTEM_DEFAULT_SLIPPAGE 3

struct SYSTEM_AckResult
{
   string status;
   int ticket;
   int error_code;
   string error_message;
   bool has_ticket;
   double fill_price;
   bool has_fill_price;
   datetime open_time;
   double volume;
   string side;
};

void SYSTEM_ResetAckResult(SYSTEM_AckResult &result)
{
   result.status = "";
   result.ticket = 0;
   result.error_code = 0;
   result.error_message = "";
   result.has_ticket = false;
   result.fill_price = 0.0;
   result.has_fill_price = false;
   result.open_time = 0;
   result.volume = 0.0;
   result.side = "";
}

string SYSTEM_BuildAckFilePath(const string account_id, const string symbol, const int magic)
{
   string filename = StringFormat(SYSTEM_ACK_FILENAME_TEMPLATE, symbol, magic);
   return SYSTEM_JoinPath(SYSTEM_BuildAccountDir(account_id), filename);
}

string SYSTEM_BuildProcessedCommandFilePath(const string account_id, const string symbol, const int magic)
{
   string filename = StringFormat(SYSTEM_PROCESSED_CMD_FILENAME_TEMPLATE, symbol, magic);
   return SYSTEM_JoinPath(SYSTEM_BuildAccountDir(account_id), filename);
}

string SYSTEM_ProcessedCommandGvName(const string account_id, const string symbol, const int magic)
{
   return "SYSTEM_CMD_" + account_id + "_" + symbol + "_" + IntegerToString(magic);
}

double SYSTEM_CommandIdHash(const string command_id)
{
   double hash = 5381.0;
   int length = StringLen(command_id);
   for(int index = 0; index < length; index++)
      hash = hash * 33.0 + (double)StringGetCharacter(command_id, index);
   return hash;
}

string SYSTEM_UIntToHex8(const uint value)
{
   string digits = "0123456789ABCDEF";
   string hex = "";
   for(int i = 0; i < 8; i++)
   {
      int nibble = (int)((value >> (28 - i * 4)) & 0xF);
      hex = hex + StringSubstr(digits, nibble, 1);
   }
   return hex;
}

string SYSTEM_BuildOpenOrderComment(const string command_id)
{
   // MT4 OrderComment limit is 31 chars. Prefer full command_id when it fits;
   // otherwise use deterministic C{hex8} matching Python build_open_order_comment.
   int length = StringLen(command_id);
   if(length > 0 && length <= 31)
      return command_id;

   uint hash = 5381;
   for(int index = 0; index < length; index++)
      hash = hash * 33 + (uint)StringGetCharacter(command_id, index);
   return "C" + SYSTEM_UIntToHex8(hash);
}

string SYSTEM_ResolveOpenOrderComment(const SYSTEM_ControlCommand &command)
{
   if(command.has_order_comment && StringLen(command.order_comment) > 0)
   {
      if(StringLen(command.order_comment) <= 31)
         return command.order_comment;
      return StringSubstr(command.order_comment, 0, 31);
   }
   return SYSTEM_BuildOpenOrderComment(command.command_id);
}

string SYSTEM_LoadProcessedCommandId(const string account_id, const string symbol, const int magic)
{
   string path = SYSTEM_BuildProcessedCommandFilePath(account_id, symbol, magic);
   string content = "";
   if(!SYSTEM_ReadTextFile(path, content))
      return "";
   if(StringLen(content) == 0)
      return "";

   int end = StringLen(content);
   while(end > 0)
   {
      int ch = StringGetCharacter(content, end - 1);
      if(ch != '\n' && ch != '\r' && ch != ' ' && ch != '\t')
         break;
      end--;
   }
   if(end <= 0)
      return "";
   return StringSubstr(content, 0, end);
}

bool SYSTEM_IsCommandProcessed(
   const string account_id,
   const string symbol,
   const int magic,
   const string command_id
)
{
   if(StringLen(command_id) == 0)
      return false;

   string gv_name = SYSTEM_ProcessedCommandGvName(account_id, symbol, magic);
   if(GlobalVariableCheck(gv_name))
   {
      if(GlobalVariableGet(gv_name) == SYSTEM_CommandIdHash(command_id))
         return true;
   }

   string persisted = SYSTEM_LoadProcessedCommandId(account_id, symbol, magic);
   return persisted == command_id;
}

void SYSTEM_MarkCommandProcessed(
   const string account_id,
   const string symbol,
   const int magic,
   const string command_id
)
{
   if(StringLen(command_id) == 0)
      return;

   string gv_name = SYSTEM_ProcessedCommandGvName(account_id, symbol, magic);
   GlobalVariableSet(gv_name, SYSTEM_CommandIdHash(command_id));

   if(SYSTEM_EnsureAccountDirectories(account_id))
   {
      string path = SYSTEM_BuildProcessedCommandFilePath(account_id, symbol, magic);
      SYSTEM_AtomicWriteText(path, command_id + "\n");
   }
}

bool SYSTEM_IsSupportedAckStatus(const string status)
{
   return status == SYSTEM_ACK_STATUS_SUCCESS
      || status == SYSTEM_ACK_STATUS_FAILED
      || status == SYSTEM_ACK_STATUS_REJECTED;
}

string SYSTEM_BuildAckJson(
   const string command_id,
   const string account_id,
   const string symbol,
   const int magic,
   const string status,
   const int ticket,
   const bool has_ticket,
   const int error_code,
   const string error_message,
   const double fill_price,
   const bool has_fill_price,
   const datetime open_time,
   const double volume,
   const string side
)
{
   string timestamp_utc = SYSTEM_FormatTimeUtc(TimeCurrent());
   int digits = (int)MarketInfo(symbol, MODE_DIGITS);
   if(digits <= 0)
      digits = 5;

   string json = "{\n";
   json = json + "  \"account_id\": \"" + SYSTEM_EscapeJsonString(account_id) + "\",\n";
   json = json + "  \"command_id\": \"" + SYSTEM_EscapeJsonString(command_id) + "\",\n";
   json = json + "  \"magic\": " + IntegerToString(magic) + ",\n";
   json = json + "  \"schema_version\": \"" + SYSTEM_EscapeJsonString(SYSTEM_PROTOCOL_SCHEMA_VERSION) + "\",\n";
   json = json + "  \"status\": \"" + SYSTEM_EscapeJsonString(status) + "\",\n";
   json = json + "  \"symbol\": \"" + SYSTEM_EscapeJsonString(symbol) + "\",\n";
   json = json + "  \"timestamp_utc\": \"" + timestamp_utc + "\"";
   if(has_ticket)
      json = json + ",\n  \"ticket\": " + IntegerToString(ticket);
   if(has_fill_price)
      json = json + ",\n  \"fill_price\": " + SYSTEM_FormatJsonNumber(fill_price, digits);
   if(open_time > 0)
      json = json + ",\n  \"open_time_utc\": \"" + SYSTEM_FormatTimeUtc(open_time) + "\"";
   if(volume > 0.0)
      json = json + ",\n  \"volume\": " + SYSTEM_FormatJsonNumber(volume, 2);
   if(StringLen(side) > 0)
      json = json + ",\n  \"side\": \"" + SYSTEM_EscapeJsonString(side) + "\"";
   if(error_code != 0)
      json = json + ",\n  \"error_code\": " + IntegerToString(error_code);
   if(StringLen(error_message) > 0)
      json = json + ",\n  \"error_message\": \"" + SYSTEM_EscapeJsonString(error_message) + "\"";
   json = json + "\n}\n";
   return json;
}

bool SYSTEM_WriteAck(
   const string account_id,
   const string symbol,
   const int magic,
   const string command_id,
   const SYSTEM_AckResult &result
)
{
   if(StringLen(account_id) == 0 || StringLen(symbol) == 0)
      return false;
   if(StringLen(command_id) == 0)
      return false;
   if(!SYSTEM_IsSupportedAckStatus(result.status))
      return false;
   if(!SYSTEM_EnsureAccountDirectories(account_id))
      return false;

   string path = SYSTEM_BuildAckFilePath(account_id, symbol, magic);
   string payload = SYSTEM_BuildAckJson(
      command_id,
      account_id,
      symbol,
      magic,
      result.status,
      result.ticket,
      result.has_ticket,
      result.error_code,
      result.error_message,
      result.fill_price,
      result.has_fill_price,
      result.open_time,
      result.volume,
      result.side
   );
   return SYSTEM_AtomicWriteText(path, payload);
}

bool SYSTEM_SelectOrderByTicket(const int ticket, const string symbol, const int magic)
{
   if(ticket <= 0)
      return false;
   if(!OrderSelect(ticket, SELECT_BY_TICKET))
      return false;
   if(OrderSymbol() != symbol)
      return false;
   if(OrderMagicNumber() != magic)
      return false;
   return true;
}

bool SYSTEM_IsSupportedTradeSide(const string side)
{
   return side == SYSTEM_SIDE_BUY || side == SYSTEM_SIDE_SELL;
}

int SYSTEM_TradeCommandForSide(const string side)
{
   if(side == SYSTEM_SIDE_BUY)
      return OP_BUY;
   if(side == SYSTEM_SIDE_SELL)
      return OP_SELL;
   return -1;
}

void SYSTEM_SetRejectedAck(SYSTEM_AckResult &result, const string message, const int error_code = 0)
{
   SYSTEM_ResetAckResult(result);
   result.status = SYSTEM_ACK_STATUS_REJECTED;
   result.error_message = message;
   result.error_code = error_code;
}

void SYSTEM_SetFailedAck(SYSTEM_AckResult &result, const string message, const int error_code)
{
   SYSTEM_ResetAckResult(result);
   result.status = SYSTEM_ACK_STATUS_FAILED;
   result.error_message = message;
   result.error_code = error_code;
}

void SYSTEM_SetSuccessAck(SYSTEM_AckResult &result, const int ticket)
{
   SYSTEM_ResetAckResult(result);
   result.status = SYSTEM_ACK_STATUS_SUCCESS;
   result.ticket = ticket;
   result.has_ticket = ticket > 0;
}

void SYSTEM_SetSuccessAckWithFill(
   SYSTEM_AckResult &result,
   const int ticket,
   const double fill_price,
   const datetime open_time,
   const double volume,
   const string side
)
{
   SYSTEM_SetSuccessAck(result, ticket);
   result.fill_price = fill_price;
   result.has_fill_price = true;
   result.open_time = open_time;
   result.volume = volume;
   result.side = side;
}

bool SYSTEM_ExecuteOpen(
   const SYSTEM_ControlCommand &command,
   SYSTEM_AckResult &result,
   string &error_message
)
{
   SYSTEM_ResetAckResult(result);
   error_message = "";

   if(!command.has_side || !SYSTEM_IsSupportedTradeSide(command.side))
   {
      SYSTEM_SetRejectedAck(result, "open command requires BUY or SELL side");
      error_message = result.error_message;
      return false;
   }
   if(!command.has_volume || command.volume <= 0.0)
   {
      SYSTEM_SetRejectedAck(result, "open command requires positive volume");
      error_message = result.error_message;
      return false;
   }
   if(!IsTradeAllowed())
   {
      SYSTEM_SetRejectedAck(result, "trade is not allowed");
      error_message = result.error_message;
      return false;
   }

   int trade_command = SYSTEM_TradeCommandForSide(command.side);
   double price = (trade_command == OP_BUY) ? MarketInfo(command.symbol, MODE_ASK) : MarketInfo(command.symbol, MODE_BID);
   double stop_loss = command.has_stop_loss ? command.stop_loss : 0.0;
   double take_profit = command.has_take_profit ? command.take_profit : 0.0;
   string order_comment = SYSTEM_ResolveOpenOrderComment(command);

   int ticket = OrderSend(
      command.symbol,
      trade_command,
      command.volume,
      price,
      SYSTEM_DEFAULT_SLIPPAGE,
      stop_loss,
      take_profit,
      order_comment,
      command.magic,
      0,
      clrNONE
   );
   if(ticket < 0)
   {
      int error_code = GetLastError();
      SYSTEM_SetFailedAck(result, "OrderSend failed", error_code);
      error_message = result.error_message;
      return false;
   }

   if(OrderSelect(ticket, SELECT_BY_TICKET))
   {
      string fill_side = (OrderType() == OP_BUY) ? SYSTEM_SIDE_BUY : SYSTEM_SIDE_SELL;
      SYSTEM_SetSuccessAckWithFill(
         result,
         ticket,
         OrderOpenPrice(),
         OrderOpenTime(),
         OrderLots(),
         fill_side
      );
   }
   else
   {
      SYSTEM_SetSuccessAck(result, ticket);
   }
   return true;
}

bool SYSTEM_ExecuteModify(
   const SYSTEM_ControlCommand &command,
   SYSTEM_AckResult &result,
   string &error_message
)
{
   SYSTEM_ResetAckResult(result);
   error_message = "";

   if(!command.has_ticket || command.ticket <= 0)
   {
      SYSTEM_SetRejectedAck(result, "modify command requires ticket");
      error_message = result.error_message;
      return false;
   }
   if(!SYSTEM_SelectOrderByTicket(command.ticket, command.symbol, command.magic))
   {
      SYSTEM_SetRejectedAck(result, "modify ticket not found for instance");
      error_message = result.error_message;
      return false;
   }

   double stop_loss = command.has_stop_loss ? command.stop_loss : OrderStopLoss();
   double take_profit = command.has_take_profit ? command.take_profit : OrderTakeProfit();
   bool modified = OrderModify(
      command.ticket,
      OrderOpenPrice(),
      stop_loss,
      take_profit,
      0,
      clrNONE
   );
   if(!modified)
   {
      int error_code = GetLastError();
      SYSTEM_SetFailedAck(result, "OrderModify failed", error_code);
      error_message = result.error_message;
      return false;
   }

   SYSTEM_SetSuccessAck(result, command.ticket);
   return true;
}

bool SYSTEM_ExecuteClose(
   const SYSTEM_ControlCommand &command,
   SYSTEM_AckResult &result,
   string &error_message
)
{
   SYSTEM_ResetAckResult(result);
   error_message = "";

   if(!command.has_ticket || command.ticket <= 0)
   {
      SYSTEM_SetRejectedAck(result, "close command requires ticket");
      error_message = result.error_message;
      return false;
   }
   if(!SYSTEM_SelectOrderByTicket(command.ticket, command.symbol, command.magic))
   {
      SYSTEM_SetRejectedAck(result, "close ticket not found for instance");
      error_message = result.error_message;
      return false;
   }

   double close_volume = command.has_volume ? command.volume : OrderLots();
   double close_price = (OrderType() == OP_BUY)
      ? MarketInfo(command.symbol, MODE_BID)
      : MarketInfo(command.symbol, MODE_ASK);
   bool closed = OrderClose(
      command.ticket,
      close_volume,
      close_price,
      SYSTEM_DEFAULT_SLIPPAGE,
      clrNONE
   );
   if(!closed)
   {
      int error_code = GetLastError();
      SYSTEM_SetFailedAck(result, "OrderClose failed", error_code);
      error_message = result.error_message;
      return false;
   }

   SYSTEM_SetSuccessAck(result, command.ticket);
   return true;
}

bool SYSTEM_ExecuteControlCommand(
   const SYSTEM_ControlCommand &command,
   SYSTEM_AckResult &result,
   string &error_message
)
{
   SYSTEM_ResetAckResult(result);
   error_message = "";

   if(command.action == SYSTEM_ACTION_NONE)
   {
      SYSTEM_SetSuccessAck(result, 0);
      return true;
   }
   if(command.action == SYSTEM_ACTION_OPEN)
      return SYSTEM_ExecuteOpen(command, result, error_message);
   if(command.action == SYSTEM_ACTION_MODIFY)
      return SYSTEM_ExecuteModify(command, result, error_message);
   if(command.action == SYSTEM_ACTION_CLOSE)
      return SYSTEM_ExecuteClose(command, result, error_message);

   SYSTEM_SetRejectedAck(result, "unsupported control action");
   error_message = result.error_message;
   return false;
}

bool SYSTEM_TryExecutePendingControl(
   const string account_id,
   const string symbol,
   const int magic,
   const string last_processed_command_id,
   string &processed_command_id,
   SYSTEM_AckResult &result,
   string &error_message
)
{
   SYSTEM_ResetAckResult(result);
   processed_command_id = "";
   error_message = "";

   SYSTEM_ControlCommand command;
   if(!SYSTEM_ReadControlCommand(account_id, symbol, magic, command, error_message))
      return false;

   if(command.command_id == last_processed_command_id
      || SYSTEM_IsCommandProcessed(account_id, symbol, magic, command.command_id))
   {
      SYSTEM_SetSuccessAck(result, 0);
      SYSTEM_WriteAck(account_id, symbol, magic, command.command_id, result);
      return false;
   }

   SYSTEM_ExecuteControlCommand(command, result, error_message);
   bool success = (result.status == SYSTEM_ACK_STATUS_SUCCESS);

   if(success)
      SYSTEM_MarkCommandProcessed(account_id, symbol, magic, command.command_id);

   if(!SYSTEM_WriteAck(account_id, symbol, magic, command.command_id, result))
   {
      error_message = "failed to write ack file";
      SYSTEM_ExportStatusWithLastError(account_id, symbol, magic, error_message);
      if(success)
      {
         processed_command_id = command.command_id;
         return true;
      }
      return false;
   }

   processed_command_id = command.command_id;
   return true;
}

bool SYSTEM_ExecutionPerformsAnalysis()
{
   return false;
}

#endif
