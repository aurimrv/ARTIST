package eu.fayder.restcountries;

import org.junit.BeforeClass;
import org.junit.Test;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import static org.junit.Assert.*;

public class RestCountriesIntegrationIT {

    private static final String BASE_URL = "http://localhost:8080";
    private static final int MAX_RETRIES = 30; // 30 tentativas
    private static final int RETRY_DELAY = 1000; // 1 segundo entre tentativas

    @BeforeClass
    public static void setup() {
        // Aguardar o servidor ficar disponível
        waitForServerToStart();
    }

    private static void waitForServerToStart() {
        for (int i = 0; i < MAX_RETRIES; i++) {
            try {
                URL url = new URL(BASE_URL + "/rest/v2/all");
                HttpURLConnection connection = (HttpURLConnection) url.openConnection();
                connection.setRequestMethod("GET");
                connection.setConnectTimeout(2000);
                connection.setReadTimeout(2000);
                
                int responseCode = connection.getResponseCode();
                if (responseCode == 200) {
                    System.out.println("Servidor disponível após " + (i + 1) + " tentativas");
                    return;
                }
            } catch (Exception e) {
                System.out.println("Tentativa " + (i + 1) + ": Servidor ainda não disponível - " + e.getMessage());
            }
            
            try {
                Thread.sleep(RETRY_DELAY);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
        }
        
        System.out.println("ATENÇÃO: Servidor pode não estar disponível após " + MAX_RETRIES + " tentativas");
    }

    // Método auxiliar para fazer requisições HTTP
    private String makeHttpRequest(String endpoint) throws IOException {
        URL url = new URL(BASE_URL + endpoint);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setRequestMethod("GET");
        connection.setRequestProperty("Accept", "application/json");
        connection.setConnectTimeout(5000);
        connection.setReadTimeout(10000);
        
        int responseCode = connection.getResponseCode();
        
        BufferedReader reader;
        if (responseCode >= 200 && responseCode < 300) {
            reader = new BufferedReader(new InputStreamReader(connection.getInputStream()));
        } else {
            reader = new BufferedReader(new InputStreamReader(connection.getErrorStream()));
        }
        
        StringBuilder response = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) {
            response.append(line);
        }
        reader.close();
        
        return response.toString();
    }

    // Método auxiliar para obter código de resposta HTTP
    private int getHttpResponseCode(String endpoint) throws IOException {
        URL url = new URL(BASE_URL + endpoint);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setRequestMethod("GET");
        connection.setRequestProperty("Accept", "application/json");
        connection.setConnectTimeout(5000);
        connection.setReadTimeout(10000);
        return connection.getResponseCode();
    }

    // Método auxiliar para verificar se o servidor está acessível
    private boolean isServerAccessible() {
        try {
            int statusCode = getHttpResponseCode("/rest/v2/all");
            return statusCode != -1 && statusCode == 200; // -1 indica erro de conexão
        } catch (Exception e) {
            return false;
        }
    }

    // Testes para o endpoint /all
    @Test(timeout = 60000)
    public void testGetAllCountries_ShouldReturnListOfCountries() throws IOException {
        String response = makeHttpRequest("/rest/v2/all");
        int statusCode = getHttpResponseCode("/rest/v2/all");
        
        assertEquals("Status code should be 200", 200, statusCode);
        assertNotNull("Response should not be null", response);
        assertTrue("Response should contain countries", response.contains("name"));
        assertTrue("Response should contain alpha2Code", response.contains("alpha2Code"));
        assertTrue("Response should contain alpha3Code", response.contains("alpha3Code"));
        assertTrue("Response should be a JSON array", response.trim().startsWith("["));
    }

    @Test(timeout = 60000)
    public void testGetAllCountries_ShouldContainBrazil() throws IOException {
        String response = makeHttpRequest("/rest/v2/all");
        int statusCode = getHttpResponseCode("/rest/v2/all");
        
        assertEquals("Status code should be 200", 200, statusCode);
        assertTrue("Response should contain Brazil", response.contains("Brazil"));
    }

    // Testes para o endpoint /name/{name}
    @Test(timeout = 60000)
    public void testGetCountryByName_ValidName_ShouldReturnCountry() throws IOException {
        String response = makeHttpRequest("/rest/v2/name/Brazil");
        int statusCode = getHttpResponseCode("/rest/v2/name/Brazil");
        
        assertEquals("Status code should be 200", 200, statusCode);
        assertNotNull("Response should not be null", response);
        assertTrue("Response should contain Brazil", response.contains("Brazil"));
        assertTrue("Response should contain BR alpha2Code", response.contains("BR"));
        assertTrue("Response should contain BRA alpha3Code", response.contains("BRA"));
    }

    @Test(timeout = 60000)
    public void testGetCountryByName_InvalidName_ShouldReturn404() throws IOException {
        int statusCode = getHttpResponseCode("/rest/v2/name/InvalidCountryName");
        assertEquals("Status code should be 404", 404, statusCode);
    }

    // Testes para o endpoint /alpha/{code}
    @Test(timeout = 60000)
    public void testGetCountryByAlphaCode_ValidAlpha2_ShouldReturnCountry() throws IOException {
        String response = makeHttpRequest("/rest/v2/alpha/br");
        int statusCode = getHttpResponseCode("/rest/v2/alpha/br");
        
        assertEquals("Status code should be 200", 200, statusCode);
        assertTrue("Response should contain Brazil", response.contains("Brazil"));
        assertTrue("Response should contain BR", response.contains("BR"));
        assertTrue("Response should contain BRA", response.contains("BRA"));
    }

    // Teste de conectividade do servidor
    @Test(timeout = 60000)
    public void testServerConnectivity_ShouldBeAccessible() throws IOException {
        try {
            int statusCode = getHttpResponseCode("/rest/v2/all");
            assertEquals("Server should return 200 OK", 200, statusCode);
            System.out.println("Server is accessible at " + BASE_URL + " with status code: " + statusCode);
        } catch (Exception e) {
            fail("Server should be accessible at " + BASE_URL + ". Error: " + e.getMessage());
        }
    }
}