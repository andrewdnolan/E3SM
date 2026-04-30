//===-- Test driver for Omega coupled driver  -----------------*- C++ -*-====//
//
/// \file
/// \brief Test driver for Omega coupled driver
///
/// This driver tests the coupled initialization path where the calendar and
/// start time are provided externally (as they would be from the MCT coupler).
/// It confirms that initialization succeeds without a StopTime/EndAlarm, that
/// the model can be stepped forward, and that finalization exits cleanly.
///
//
//===-----------------------------------------------------------------------===/

#include "IOStream.h"
#include "OceanDriver.h"
#include "OceanState.h"
#include "OmegaKokkos.h"
#include "Pacer.h"
#include "TimeMgr.h"
#include "TimeStepper.h"
#include <mpi.h>

//------------------------------------------------------------------------------
// The test driver for the coupled driver
//
int main(int argc, char *argv[]) {

   OMEGA::I4 ErrAll;
   OMEGA::I4 ErrCurr;
   OMEGA::I4 ErrFinalize;

   MPI_Init(&argc, &argv); // initialize MPI
   Kokkos::initialize();   // initialize Kokkos
   Pacer::initialize(MPI_COMM_WORLD);
   Pacer::setPrefix("Omega:");

   // Mock arguments coming from the coupled driver
   int OcnId                   = 0;
   std::string CalendarKindStr = "No Leap";
   std::string ConfigFile      = "omega.yml";
   std::string LogFile         = "ocn.log";
   int CurrYMD                 = 10101; // "0001-01-01" in YMD formatk
   int CurrTOD                 = 0;     // "00:00:00" in TOD format

   OMEGA::I4 Year   = (CurrYMD / 100) / 100;
   OMEGA::I4 Month  = (CurrYMD / 100) % 100;
   OMEGA::I4 Day    = CurrYMD % 100;
   OMEGA::I4 Hour   = (CurrTOD / 60) / 60;
   OMEGA::I4 Minute = (CurrTOD / 60) % 60;
   OMEGA::R8 Second = CurrTOD % 60;

   // In coupled mode the coupler owns the calendar and start time.
   // These must be initialized before ocnInit is called.
   OMEGA::Calendar::init("No Leap");
   OMEGA::TimeInstant StartTime(Year, Month, Day, Hour, Minute, Second);

   Pacer::start("Init", 0);
   ErrCurr =
       OMEGA::ocnInit(MPI_COMM_WORLD, OcnId, ConfigFile, LogFile, StartTime);
   if (ErrCurr == 0) {
      LOG_INFO("CoupledDriverTest: Omega initialize PASS");
   } else {
      LOG_INFO("CoupledDriverTest: Omega initialize FAIL");
   }
   Pacer::stop("Init", 0);

   // Verify the stepper has no EndAlarm — in coupled mode the coupler
   // controls run length, not an internal alarm.
   OMEGA::TimeStepper *DefStepper = OMEGA::TimeStepper::getDefault();
   OMEGA::Clock *ModelClock       = DefStepper->getClock();
   OMEGA::TimeInstant CurrTime    = ModelClock->getCurrentTime();

   if (ErrCurr == 0 && DefStepper->hasEndAlarm()) {
      LOG_ERROR("CoupledDriverTest: hasEndAlarm() should be false in coupled "
                "mode");
      ErrCurr++;
   }

   // Step the model forward a few times to simulate coupling intervals.
   // ocnRun(CurrTime, NextCouplingTime) will replace this loop once
   // the coupled ocnRun overload is implemented.
   Pacer::start("RunLoop", 0);
   if (ErrCurr == 0) {
      OMEGA::OceanState *DefState = OMEGA::OceanState::getDefault();
      for (int Step = 0; Step < 3; ++Step) {
         DefStepper->doStep(DefState, CurrTime);
         OMEGA::IOStream::writeAll(ModelClock);
      }
      LOG_INFO("CoupledDriverTest: Omega model run PASS");
   } else {
      LOG_INFO("CoupledDriverTest: Omega model run FAIL");
   }
   Pacer::stop("RunLoop", 0);

   Pacer::start("Finalize", 0);
   ErrFinalize = OMEGA::ocnFinalize(CurrTime);
   if (ErrFinalize == 0) {
      LOG_INFO("CoupledDriverTest: Omega finalize PASS");
   } else {
      LOG_INFO("CoupledDriverTest: Omega finalize FAIL");
   }
   Pacer::stop("Finalize", 0);

   ErrAll = abs(ErrCurr) + abs(ErrFinalize);
   if (ErrAll == 0) {
      LOG_INFO("CoupledDriverTest: Successful completion");
   }

   Pacer::print("omega_coupled_driver_test", OMEGA::printTimingAllRanks());
   Pacer::finalize();

   Kokkos::finalize();
   MPI_Finalize();

   if (ErrAll >= 256)
      ErrAll = 255;
   return ErrAll;

} // end of main
//===-----------------------------------------------------------------------===/
