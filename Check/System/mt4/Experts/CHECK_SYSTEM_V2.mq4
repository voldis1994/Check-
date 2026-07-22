#property copyright "Check System"
#property link      "https://github.com/voldis1994/Check-"
#property version   "2.0.0"
#property strict

#include <CHECK_Protocol.mqh>
#include <CHECK_Export.mqh>
#include <CHECK_Execution.mqh>

input int    MagicNumber     = 19942026;
input string BridgeRootPath  = ""; // absolute path to Check/System root (folder that contains runtime/)

int OnInit()
{
   if(Period() != PERIOD_M1)
   {
      Print("CHECK_SYSTEM_V2 requires M1 chart");
      return(INIT_FAILED);
   }
   if(StringLen(BridgeRootPath) == 0)
   {
      Print("BridgeRootPath must be set to SYSTEM root");
      return(INIT_PARAMETERS_INCORRECT);
   }

   // Absolute bridge IO uses kernel32.dll — enable "Allow DLL imports" for this EA.
   CHECK_InitBridge(BridgeRootPath, Symbol(), MagicNumber);
   if(!CHECK_EnsureBridgeDirectories())
   {
      Print("CHECK_SYSTEM_V2: failed to create bridge directories under ", BridgeRootPath);
      Print("Ensure Allow DLL imports is enabled and the path is writable.");
      return(INIT_FAILED);
   }

   Print(
      "CHECK_SYSTEM_V2 initialized protocol=", CHECK_ProtocolVersion(),
      " symbol=", Symbol(),
      " magic=", MagicNumber,
      " account=", AccountNumber(),
      " bridge=", BridgeRootPath
   );
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
}

void OnTick()
{
   CHECK_ExportMarketAndStatus();
   CHECK_TryExecutePendingCommands();
}
