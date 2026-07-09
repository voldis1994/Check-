#property copyright "SYSTEM"
#property link      "https://github.com/voldis1994/VS_READER_ENGINE_V2"
#property version   "1.00"
#property strict

input int MagicNumber = 100001;
input string SystemRootPath = "";

#include <SYSTEM_Execution.mqh>
#include <SYSTEM_Universe.mqh>

datetime g_last_exported_bar_time = 0;
string g_last_processed_command_id = "";

int OnInit()
{
   if(Period() != PERIOD_M1)
   {
      Print("SYSTEM_EA requires M1 timeframe");
      return INIT_FAILED;
   }

   if(StringLen(SystemRootPath) > 0)
      SYSTEM_ConfigureRootPath(SystemRootPath);

   if(!SYSTEM_InitPaths())
   {
      Print("SYSTEM path initialization failed");
      return INIT_FAILED;
   }

   return INIT_SUCCEEDED;
}

void OnTick()
{
   string account_id = IntegerToString(AccountNumber());
   string symbol = Symbol();
   int magic = MagicNumber;

   if(SYSTEM_IsNewM1Bar(symbol, g_last_exported_bar_time))
   {
      if(!SYSTEM_ExportMarketAndSensor(account_id, symbol, magic))
      {
         Print("SYSTEM export failed for ", symbol, " magic=", magic);
         return;
      }

      if(!SYSTEM_ExportStatus(account_id, symbol, magic))
      {
         Print("SYSTEM status export failed for account ", account_id);
         return;
      }

      if(!SYSTEM_ExportUniverse(account_id))
      {
         Print("SYSTEM universe export failed for account ", account_id);
         return;
      }

      g_last_exported_bar_time = iTime(symbol, PERIOD_M1, 0);
   }

   SYSTEM_AckResult ack_result;
   string processed_command_id = "";
   string error_message = "";
   if(SYSTEM_TryExecutePendingControl(
      account_id,
      symbol,
      magic,
      g_last_processed_command_id,
      processed_command_id,
      ack_result,
      error_message
   ))
   {
      g_last_processed_command_id = processed_command_id;
   }
}

void OnDeinit(const int reason)
{
}
