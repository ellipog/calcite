import java.io.BufferedWriter;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

// Prints the name Java's Character.getName gives each code point that has one, as
// "<hex>;<name>" lines, for names.py. Black-box: it only calls the JDK's public API.
public class Names {
    public static void main(String[] args) throws Exception {
        BufferedWriter out = new BufferedWriter(new OutputStreamWriter(System.out, StandardCharsets.UTF_8));
        for (int cp = 0; cp <= Character.MAX_CODE_POINT; cp++) {
            String name = Character.getName(cp);
            if (name != null) {
                out.write(String.format(Locale.ROOT, "%X;%s\n", cp, name));
            }
        }
        out.flush();
    }
}
