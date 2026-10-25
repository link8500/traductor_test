#include "translation_coverage.h"
#include <iostream>
#include <stdexcept>
int main() try {
  size_t count=0;
  auto check=[&](bool ok){++count;if(!ok)throw std::runtime_error("Coverage policy guard failed: "+std::to_string(count));};
  using namespace luma::coverage;
  auto source="THE TRAIN IS HERE. WE SHOULD LEAVE NOW.";
  auto parts=Sentences(source);
  check(parts.size()==2);
  check(Retry(source,"Debemos irnos ya.",parts));
  check(!Retry(source,"El tren llegó, debemos irnos.",parts));
  check(!Retry(source,"El tren ya ha llegado. Debemos salir ahora mismo.",parts));
  check(Sentences("PLEASE STOP HERE. WAIT FOR ME").empty());
  check(Sentences("PLEASE STOP HERE... WAIT FOR ME.").empty());
  check(Sentences("NO. WAIT FOR ME.").empty());
  check(Sentences("WE SAW MR. GREEN AT HOME. WE SHOULD LEAVE NOW.").size()==2);
  check(Sentences("WE SAW A. GREEN AT HOME. WE SHOULD LEAVE NOW.").size()==2);
  check(Sentences("PLEASE STOP HERE. WE SHOULD LEAVE NOW. WAIT FOR YOUR FRIEND. I WILL STAY HERE.").size()==4);
  check(Sentences("PLEASE STOP HERE. WE SHOULD LEAVE NOW. WAIT FOR YOUR FRIEND. I WILL STAY HERE. THIS IS THE END.").empty());
  check(Sentences("PLEASE STOP HERE. \"WE SHOULD LEAVE NOW.\"").size()==2);
  check(Clauses("Una cosa, otra cosa.")==2);
  check(Clauses("¿De veras...? ¡Claro que sí!")==2);
  check(Clauses("El valor es 1.25.")==1);
  check(Letters("Leave now!")==Letters("LEAVE NOW."));
  check(!Retry("", "", {}));
  auto questions="WHERE DID YOU GO? WE WAITED FOR YOU AT THE STATION.";
  check(Retry(questions,"Te esperamos durante mucho tiempo en la estaci\xc3\xb3n.",Sentences(questions)));
  check(!Retry(questions,"\xc2\xbf" "Ad\xc3\xb3nde fuiste? Te esperamos en la estaci\xc3\xb3n.",Sentences(questions)));
  check(Sentences("PLEASE STOP HERE. WE WILL WAIT FOR YOU").size()==2);
  check(Sentences("PLEASE STOP HERE. WE WILL WAIT FOR YOU,").size()==2);
  check(Sentences("PLEASE STOP HERE... WE WILL WAIT FOR YOU").empty());
  check(Sentences("PLEASE STOP HERE. WE WILL WAIT FOR YOU...").empty());
  check(Sentences("COME NOW? WE WILL WAIT FOR YOU.").size()==2);
  check(Sentences("WE AGREE. WE WILL WAIT FOR YOU.").size()==2);
  auto short_question="COME NOW? WE WILL WAIT FOR YOU.";
  check(Retry(short_question,"Te esperamos en este lugar.",Sentences(short_question)));
  check(!Retry(short_question,"Ven ahora. Te esperamos en este lugar?",Sentences(short_question)));
  auto conditional="WE MUST DEPART NOW. IF WE STAY HERE, WE WILL LOSE.";
  check(Retry(conditional,"Si seguimos, perderemos.",Sentences(conditional)));
  check(!Plausible("ONE SHORT EXPRESSION.","Ay, ay, ay, ay, ay, ay, ay."));
  check(!Plausible("WE MUST LEAVE.","Ve ahora ve ahora ve ahora ve ahora."));
  check(Plausible("HA HA HA HA HA!","Ha, ha, ha, ha, ha!"));
  check(Plausible("WE MUST LEAVE.","Tenemos que irnos."));
  check(LongClauseRetry(source,"Debemos irnos ya.",parts));
  check(!LongClauseRetry(short_question,"Te esperamos en este lugar.",Sentences(short_question)));
  check(NormalizedWords("¡ÉL, TÚ! ¿Niño? 42")==std::vector<std::u32string>({U"él",U"tú",U"niño",U"42"}));
  check(PreservesExistingWords("Te esperamos.","Ven ahora. Te esperamos."));
  check(!PreservesExistingWords("El tren partió, espera aquí.","El tren partió. Esperas lo que miras."));
  check(!PreservesExistingWords("Tú vienes conmigo, dormirás bien.","Es tarde. Yo vengo conmigo, yo duermo bien."));
  check(!PreservesExistingWords("Sí sí sí, puedes ir.","Sí, puedes ir ahora mismo."));
  check(PreservesExistingWords("Debemos ir a casa ahora.","Tenemos que salir. Debemos ir a casa ahora."));
  check(PreservesNegation("WHY NOT?","¿Por qué no?"));
  check(!PreservesNegation("WHY NOT?","¿Por qué?"));
  check(PreservesNegation("DON'T GO!","¡No vayas!"));
  check(!PreservesNegation("DON’T GO!","¡Vete!"));
  check(PreservesNegation("NEVER GO THERE.","Jamás vayas allí."));
  check(PreservesNegation("WE SHOULD GO.","Deberíamos ir."));
  std::cout<<"{\"success\":true,\"guards\":"<<count<<",\"model_inference\":false}"<<std::endl;
} catch(const std::exception& error) {
  std::cerr<<error.what()<<std::endl;
  return 1;
}
