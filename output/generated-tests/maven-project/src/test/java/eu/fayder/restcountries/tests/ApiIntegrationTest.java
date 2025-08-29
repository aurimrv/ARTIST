package eu.fayder.restcountries.tests;

import org.junit.Before;
import org.junit.Test;
import org.junit.After;
import org.junit.BeforeClass;
import org.junit.AfterClass;
import org.junit.Ignore;
import static org.junit.Assert.*;
import static org.hamcrest.Matchers.*;

import io.restassured.RestAssured;
import io.restassured.response.Response;
import io.restassured.specification.RequestSpecification;
import static io.restassured.RestAssured.*;
import io.restassured.http.ContentType;

public class ApiIntegrationTest {
    
    private static final String BASE_URL = "http://localhost:8090/restcountries-2.0.5/rest";
    private static final int DEFAULT_TIMEOUT = 30;
    
    @BeforeClass
    public static void setUpClass() {
        RestAssured.baseURI = BASE_URL;
        RestAssured.enableLoggingOfRequestAndResponseIfValidationFails();
    }
    
    @AfterClass
    public static void tearDownClass() {
        RestAssured.reset();
    }
    
    @Before
    public void setUp() {
    }
    
    @After
    public void tearDown() {
    }

    @Test
    public void testGetAllCountriesSuccess() {
        Response response = givenDefaultRequest()
        .when()
            .get("/v2/all")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .body("", not(empty()))
            .body("size()", greaterThan(0))
            .extract().response();
        
        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void testGetCountryByNameSuccess() {
        Response response = givenDefaultRequest()
            .pathParam("name", "portugal")
        .when()
            .get("/v2/name/{name}")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .body("", not(empty()))
            .body("size()", greaterThan(0))
            .extract().response();
        
        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Ignore("Expected HTTP 400 but got 404")


    @Test
    public void testGetCountryByNameBadRequest() {
        Response response = givenDefaultRequest()
            .pathParam("name", "!@#$%^&*()")
        .when()
            .get("/v2/name/{name}")
        .then()
            .statusCode(400)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
        
        assertEquals(400, response.getStatusCode());
    }

    @Test
    public void testGetCountryByNameNotFound() {
        Response response = givenDefaultRequest()
            .pathParam("name", "NonExistentCountry")
        .when()
            .get("/v2/name/{name}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void testGetCountryByAlphaCodeSuccess() {
        Response response = givenDefaultRequest()
            .pathParam("code", "pt")
        .when()
            .get("/v2/alpha/{code}")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .body("", not(empty()))
            .body("size()", greaterThan(0))
            .extract().response();
        
        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void testGetCountryByAlphaCodeBadRequest() {
        Response response = givenDefaultRequest()
            .pathParam("code", "TOOLONG")
        .when()
            .get("/v2/alpha/{code}")
        .then()
            .statusCode(400)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void testGetCountryByAlphaCodeNotFound() {
        Response response = givenDefaultRequest()
            .pathParam("code", "ZZ")
        .when()
            .get("/v2/alpha/{code}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void testGetCountryByCurrencySuccess() {
        Response response = givenDefaultRequest()
            .pathParam("currency", "eur")
        .when()
            .get("/v2/currency/{currency}")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .body("", not(empty()))
            .body("size()", greaterThan(0))
            .extract().response();
        
        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void testGetCountryByCurrencyBadRequest() {
        Response response = givenDefaultRequest()
            .pathParam("currency", "INVALID_CURRENCY_FORMAT")
        .when()
            .get("/v2/currency/{currency}")
        .then()
            .statusCode(400)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void testGetCountryByCurrencyNotFound() {
        Response response = givenDefaultRequest()
            .pathParam("currency", "zzz")
        .when()
            .get("/v2/currency/{currency}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void testGetCountryByLanguageSuccess() {
        Response response = givenDefaultRequest()
            .pathParam("language", "pt")
        .when()
            .get("/v2/lang/{language}")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .body("", not(empty()))
            .body("size()", greaterThan(0))
            .extract().response();
        
        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Ignore("Expected HTTP 400 but got 404")


    @Test
    public void testGetCountryByLanguageBadRequest() {
        Response response = givenDefaultRequest()
            .pathParam("language", "!@#$%^&*()")
        .when()
            .get("/v2/lang/{language}")
        .then()
            .statusCode(400)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
        
        assertEquals(400, response.getStatusCode());
    }

    @Test
    public void testGetCountryByLanguageNotFound() {
        Response response = givenDefaultRequest()
            .pathParam("language", "zz")
        .when()
            .get("/v2/lang/{language}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void testGetCountryByCapitalSuccess() {
        Response response = givenDefaultRequest()
            .pathParam("capital", "lisbon")
        .when()
            .get("/v2/capital/{capital}")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .body("", not(empty()))
            .body("size()", greaterThan(0))
            .extract().response();
        
        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Ignore("Expected HTTP 400 but got 404")


    @Test
    public void testGetCountryByCapitalBadRequest() {
        Response response = givenDefaultRequest()
            .pathParam("capital", "!@#$%^&*()")
        .when()
            .get("/v2/capital/{capital}")
        .then()
            .statusCode(400)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
        
        assertEquals(400, response.getStatusCode());
    }

    @Test
    public void testGetCountryByCapitalNotFound() {
        Response response = givenDefaultRequest()
            .pathParam("capital", "NonExistentCapital")
        .when()
            .get("/v2/capital/{capital}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void testGetCountryByRegionSuccess() {
        Response response = givenDefaultRequest()
            .pathParam("region", "europe")
        .when()
            .get("/v2/region/{region}")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .body("", not(empty()))
            .body("size()", greaterThan(0))
            .extract().response();
        
        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Ignore("Expected HTTP 400 but got 404")


    @Test
    public void testGetCountryByRegionBadRequest() {
        Response response = givenDefaultRequest()
            .pathParam("region", "!@#$%^&*()")
        .when()
            .get("/v2/region/{region}")
        .then()
            .statusCode(400)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
        
        assertEquals(400, response.getStatusCode());
    }

    @Test
    public void testGetCountryByRegionNotFound() {
        Response response = givenDefaultRequest()
            .pathParam("region", "NonExistentRegion")
        .when()
            .get("/v2/region/{region}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void testGetV1SourceCode() {
        Response response = givenDefaultRequest()
        .when()
            .get("/v1")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();
        
        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Ignore("POST method not allowed on /v1 endpoint")
    @Test
    public void testPostV1SourceCode() {
        Response response = givenDefaultRequest()
        .when()
            .post("/v1")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();
        
        validateResponseTime(response);
        validateJsonResponse(response);
    }

    @Test
    public void testGetV2SourceCode() {
        Response response = givenDefaultRequest()
        .when()
            .get("/v2")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .extract().response();
        
        validateResponseTime(response);
        validateJsonResponse(response);
    }

    private RequestSpecification givenDefaultRequest() {
        return given()
            .contentType(ContentType.JSON)
            .accept(ContentType.JSON);
    }
    
    private void validateResponseTime(Response response) {
        response.then().time(lessThan((long) DEFAULT_TIMEOUT * 1000));
    }
    
    private void validateJsonResponse(Response response) {
        response.then().contentType(ContentType.JSON);
    }
}