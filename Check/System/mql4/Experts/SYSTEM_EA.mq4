#property copyright "SYSTEM"
#property link      "https://github.com/voldis1994/Check-"
#property version   "1.01"
#property strict

input int MagicNumber = 100001;
input string SystemRootPath = "";

#include <SYSTEM_Execution.mqh>
#include <SYSTEM_Universe.mqh>

datetime g_last_exported_bar_time = 0;
string g_last_processed_command_id = "";
bool g_export_ok_once = false;

bool SYSTEM_RunExportCycle()
{
   string account_id = IntegerToString(AccountNumber());
   string symbol = Symbol();
   int magic = MagicNumber;

   if(!SYSTEM_ExportMarketAndSensor(account_id, symbol, magic))
   {
      Print("SYSTEM export failed for ", symbol, " magic=", magic, " root=", SYSTEM_GetRootPath());
      return false;
   }

   if(!SYSTEM_ExportStatus(account_id, symbol, magic))
   {
      Print("SYSTEM status export failed for account ", account_id);
      return false;
   }

   if(!SYSTEM_ExportUniverse(account_id))
   {
      Print("SYSTEM universe export failed for account ", account_id);
      return false;
   }

   g_last_exported_bar_time = iTime(symbol, PERIOD_M1, 0);
   if(!g_export_ok_once)
   {
      g_export_ok_once = true;
      Print("SYSTEM export OK -> ", SYSTEM_BuildMarketFilePath(account_id, symbol, magic));
      Print("SYSTEM also mirrors under Terminal Common\\Files\\CheckSystem\\ if DLL write is blocked");
   }
   return true;
}

int OnInit()
{
   if(Period() != PERIOD_M1)
   {
      Print("SYSTEM_EA requires M1 timeframe");
      return INIT_FAILED;
   }

   if(StringLen(SystemRootPath) > 0)
      SYSTEM_ConfigureRootPath(SystemRootPath);

   Print("SYSTEM root=", SYSTEM_GetRootPath(), " symbol=", Symbol(), " magic=", MagicNumber, " account=", AccountNumber());
   Print("SYSTEM tip: enable Allow DLL imports; if blocked, Common\\Files\\CheckSystem fallback is used");

   if(!SYSTEM_InitPaths())
   {
      Print("SYSTEM path initialization via DLL failed — continuing with Common\\Files fallback");
   }

   // Do not wait for the next M1 bar — write immediately so Python can start.
   SYSTEM_RunExportCycle();

   EventSetTimer(1);
   return INIT_SUCCEEDED;
}

void OnTimer()
{
   // Keep trying until first success, then also refresh mid-bar sensor/status every few seconds.
   if(!g_export_ok_once)
   {
      SYSTEM_RunExportCycle();
      return;
   }

   string account_id = IntegerToString(AccountNumber());
   string symbol = Symbol();
   int magic = MagicNumber;
   SYSTEM_ExportSensorReading(account_id, symbol, magic);
   SYSTEM_ExportStatus(account_id, symbol, magic);
}

void OnTick()
{
   if(SYSTEM_IsNewM1Bar(Symbol(), g_last_exported_bar_time))
      SYSTEM_RunExportCycle();

   SYSTEM_AckResult ack_result;
   string processed_command_id = "";
   string error_message = "";
   if(SYSTEM_TryExecutePendingControl(
      IntegerToString(AccountNumber()),
      Symbol(),
      MagicNumber,
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
   EventKillTimer();
}
