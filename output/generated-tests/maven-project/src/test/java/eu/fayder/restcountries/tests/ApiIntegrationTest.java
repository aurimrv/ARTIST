package eu.fayder.restcountries.tests;

import org.junit.Before;
import org.junit.Test;
import org.junit.After;
import org.junit.BeforeClass;
import org.junit.AfterClass;
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
    public void testGetAllSuccess() {
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
    public void testGetAllInvalidParams() {
        Response response = givenDefaultRequest()
            .queryParam("invalid", "parameter")
        .when()
            .get("/v2/all")
        .then()
            .statusCode(400)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void testGetNameSuccess() {
        Response response = givenDefaultRequest()
            .pathParam("name", "sample_value")
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

    @Test
    public void testGetNameInvalidParams() {
        Response response = givenDefaultRequest()
            .pathParam("name", "test")
            .queryParam("invalid", "parameter")
        .when()
            .get("/v2/name/{name}")
        .then()
            .statusCode(400)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void testGetNameNotFound() {
        Response response = givenDefaultRequest()
            .pathParam("name", "NonExistentResource")
        .when()
            .get("/v2/name/{name}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void testGetAlphaSuccess() {
        Response response = givenDefaultRequest()
            .pathParam("code", "sample_value")
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
    public void testGetAlphaInvalidParams() {
        Response response = givenDefaultRequest()
            .pathParam("code", "TEST")
            .queryParam("invalid", "parameter")
        .when()
            .get("/v2/alpha/{code}")
        .then()
            .statusCode(400)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void testGetAlphaNotFound() {
        Response response = givenDefaultRequest()
            .pathParam("code", "INVALID")
        .when()
            .get("/v2/alpha/{code}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void testGetCurrencySuccess() {
        Response response = givenDefaultRequest()
            .pathParam("currency", "sample_value")
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
    public void testGetCurrencyInvalidParams() {
        Response response = givenDefaultRequest()
            .pathParam("currency", "sample")
            .queryParam("invalid", "parameter")
        .when()
            .get("/v2/currency/{currency}")
        .then()
            .statusCode(400)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void testGetCurrencyNotFound() {
        Response response = givenDefaultRequest()
            .pathParam("currency", "NotFound")
        .when()
            .get("/v2/currency/{currency}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void testGetLangSuccess() {
        Response response = givenDefaultRequest()
            .pathParam("language", "sample_value")
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

    @Test
    public void testGetLangInvalidParams() {
        Response response = givenDefaultRequest()
            .pathParam("language", "sample")
            .queryParam("invalid", "parameter")
        .when()
            .get("/v2/lang/{language}")
        .then()
            .statusCode(400)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void testGetLangNotFound() {
        Response response = givenDefaultRequest()
            .pathParam("language", "NotFound")
        .when()
            .get("/v2/lang/{language}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void testGetCapitalSuccess() {
        Response response = givenDefaultRequest()
            .pathParam("capital", "sample_value")
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

    @Test
    public void testGetCapitalInvalidParams() {
        Response response = givenDefaultRequest()
            .pathParam("capital", "sample")
            .queryParam("invalid", "parameter")
        .when()
            .get("/v2/capital/{capital}")
        .then()
            .statusCode(400)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void testGetCapitalNotFound() {
        Response response = givenDefaultRequest()
            .pathParam("capital", "NotFound")
        .when()
            .get("/v2/capital/{capital}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void testGetRegionSuccess() {
        Response response = givenDefaultRequest()
            .pathParam("region", "sample_value")
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

    @Test
    public void testGetRegionInvalidParams() {
        Response response = givenDefaultRequest()
            .pathParam("region", "sample")
            .queryParam("invalid", "parameter")
        .when()
            .get("/v2/region/{region}")
        .then()
            .statusCode(400)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
    }

    @Test
    public void testGetRegionNotFound() {
        Response response = givenDefaultRequest()
            .pathParam("region", "NotFound")
        .when()
            .get("/v2/region/{region}")
        .then()
            .statusCode(404)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .extract().response();
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