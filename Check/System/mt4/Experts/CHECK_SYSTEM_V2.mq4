#property copyright "Check System"
#property link      "https://github.com/voldis1994/Check-"
#property version   "2.0.0"
#property strict

#include <CHECK_Protocol.mqh>
#include <CHECK_Export.mqh>
#include <CHECK_Execution.mqh>

input int    MagicNumber     = 19942026;
// Leave empty = AUTO under Terminal Data Folder\MQL4\Files\CHECK_SYSTEM
// Or set to Check\System folder (the folder that contains runtime\)
input string BridgeRootPath  = "";

string CHECK_ResolveBridgeRoot()
{
   if(StringLen(BridgeRootPath) > 0)
      return BridgeRootPath;
   // AUTO: Terminal data folder is always known to the EA — no manual path needed.
   string data_path = TerminalInfoString(TERMINAL_DATA_PATH);
   if(StringLen(data_path) == 0)
      return "";
   return data_path + "\\MQL4\\Files\\CHECK_SYSTEM";
}

int OnInit()
{
   if(Period() != PERIOD_M1)
   {
      Print("CHECK_SYSTEM_V2 requires M1 chart");
      return(INIT_FAILED);
   }

   string root = CHECK_ResolveBridgeRoot();
   if(StringLen(root) == 0)
   {
      Print("CHECK_SYSTEM_V2: cannot resolve bridge root (TERMINAL_DATA_PATH empty)");
      return(INIT_FAILED);
   }

   // Absolute bridge IO uses kernel32.dll — enable "Allow DLL imports" for this EA.
   CHECK_InitBridge(root, Symbol(), MagicNumber);
   if(!CHECK_EnsureBridgeDirectories())
   {
      Print("CHECK_SYSTEM_V2: failed to create bridge directories under ", root);
      Print("Enable Allow DLL imports on the EA Common tab, then re-attach.");
      return(INIT_FAILED);
   }

   // Smoke-write so Python can discover this bridge immediately.
   CHECK_ExportMarketAndStatus();

   Print(
      "CHECK_SYSTEM_V2 initialized protocol=", CHECK_ProtocolVersion(),
      " symbol=", Symbol(),
      " magic=", MagicNumber,
      " account=", AccountNumber(),
      " bridge=", root,
      " (BridgeRootPath empty=AUTO)"
   );
   Comment("CHECK V2 bridge=", root);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   Comment("");
}

void OnTick()
{
   CHECK_ExportMarketAndStatus();
   CHECK_TryExecutePendingCommands();
}
