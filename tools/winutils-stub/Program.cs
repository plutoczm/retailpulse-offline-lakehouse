using System;

namespace RetailPulse.WinutilsStub
{
    internal static class Program
    {
        private static int Main(string[] args)
        {
            // Spark on Windows calls winutils.exe for local permission commands.
            // For this local-only demo pipeline, a successful no-op is enough.
            if (args.Length > 0 && args[0].Equals("ls", StringComparison.OrdinalIgnoreCase))
            {
                return 1;
            }

            return 0;
        }
    }
}

