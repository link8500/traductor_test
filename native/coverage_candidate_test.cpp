#include "translation_coverage_candidate.h"
#include <iostream>
#include <stdexcept>
int main() {
  using namespace luma::coverage_candidate;
  size_t n=0;auto check=[&](bool ok){++n;if(!ok)throw std::runtime_error("Coverage candidate guard "+std::to_string(n));};
  auto source="WHERE DID YOU GO? WE WAITED FOR YOU AT THE STATION.";
  auto parts=Sentences(source);check(parts.size()==2);
  check(Retry(source,"Te esperamos durante mucho tiempo en la estaci\xc3\xb3n.",parts));
  check(!Retry(source,"\xc2\xbf" "Ad\xc3\xb3nde fuiste? Te esperamos en la estaci\xc3\xb3n.",parts));
  check(Sentences("PLEASE STOP HERE. WAIT FOR ME").empty());
  check(Sentences("PLEASE STOP HERE. WE WILL WAIT FOR YOU").size()==2);
  check(Sentences("PLEASE STOP HERE. WE WILL WAIT FOR YOU,").size()==2);
  check(Sentences("PLEASE STOP HERE... WE WILL WAIT FOR YOU").empty());
  check(Sentences("PLEASE STOP HERE. WE WILL WAIT FOR YOU...").empty());
  check(Sentences("WE SAW MR. GREEN AT HOME. WE SHOULD LEAVE NOW.").size()==2);
  check(Sentences("WE SAW A. GREEN AT HOME. WE SHOULD LEAVE NOW.").size()==2);
  check(Sentences("NO. WE WILL WAIT FOR YOU").empty());
  check(!Retry("", "", {}));
  check(!Retry("WAIT FOR ME.","Esp\xc3\xa9rame.",{}));
  std::cout<<"{\"success\":true,\"guards\":"<<n<<",\"application_enabled\":false}"<<std::endl;
}
