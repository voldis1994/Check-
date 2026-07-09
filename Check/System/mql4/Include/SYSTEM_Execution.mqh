#ifndef __SYSTEM_EXECUTION_MQH__
#define __SYSTEM_EXECUTION_MQH__

#property strict

#include <SYSTEM_Control.mqh>
#include <SYSTEM_Status.mqh>

#define SYSTEM_ACK_FILENAME_TEMPLATE "ack_%s_%d.json"
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
};

void SYSTEM_ResetAckResult(SYSTEM_AckResult &result)
{
   result.status = "";
   result.ticket = 0;
   result.error_code = 0;
   result.error_message = "";
   result.has_ticket = false;
}

string SYSTEM_BuildAckFilePath(const string account_id, const string symbol, const int magic)
{
   string filename = StringFormat(SYSTEM_ACK_FILENAME_TEMPLATE, symbol, magic);
   return SYSTEM_JoinPath(SYSTEM_BuildAccountDir(account_id), filename);
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
   const string error_message
)
{
   string timestamp_utc = SYSTEM_FormatTimeUtc(TimeCurrent());
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
      result.error_message
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

   int ticket = OrderSend(
      command.symbol,
      trade_command,
      command.volume,
      price,
      SYSTEM_DEFAULT_SLIPPAGE,
      stop_loss,
      take_profit,
      command.reason,
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

   SYSTEM_SetSuccessAck(result, ticket);
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

   if(command.command_id == last_processed_command_id)
      return false;

   SYSTEM_ExecuteControlCommand(command, result, error_message);
   if(!SYSTEM_WriteAck(account_id, symbol, magic, command.command_id, result))
   {
      error_message = "failed to write ack file";
      SYSTEM_ExportStatusWithLastError(account_id, symbol, magic, error_message);
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
